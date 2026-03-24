import os
import uuid
import json
import re
import zipfile
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
import pandas as pd
from io import BytesIO
from ...core.database import get_db
from ...models.user import User
from ...models.report import Report
from ...models.import_task import ImportTask
from ...models.annotation import Annotation
from ...schemas.report import (
    ReportResponse, ReportListResponse,
    ImportTaskResponse, AssignRequest, AssignResponse
)
from ..deps import get_current_user, require_role

router = APIRouter()

# 报告状态
STATUS_IMPORTED = "IMPORTED"
STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_REVIEW_ASSIGNED = "REVIEW_ASSIGNED"
STATUS_REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
STATUS_DONE = "DONE"

# 导入任务状态
TASK_PENDING = "PENDING"
TASK_RUNNING = "RUNNING"
TASK_SUCCESS = "SUCCESS"
TASK_FAILED = "FAILED"


# 表头映射 - 支持英文和中文
COLUMN_MAPPING = {
    # 英文表头 (新)
    "RIS_NO": "ris_no",
    "MODALITY": "modality",
    "PATIENT_SEX": "patient_sex",
    "PATIENT_AGE": "patient_age",
    "EXAM_ITEM": "exam_item",
    "EXAM_MODE": "exam_mode",
    "EXAM_GROUP": "exam_group",
    "DESCRIPTION": "description",
    "IMPRESSION": "impression",

    # 中文表头 (兼容)
    "检查号": "ris_no",
    "检查类型": "modality",
    "性别": "patient_sex",
    "年龄": "patient_age",
    "检查项目": "exam_item",
    "检查模式": "exam_mode",
    "检查组": "exam_group",
    "检查所见": "description",
    "诊断意见": "impression",

    # 旧字段兼容
    "报告全文": "report_text",
    "报告内容": "report_text",
    "报告文本": "report_text",
    "报告": "report_text",
    "report_text": "report_text",
    "text": "report_text",
    "报告ID": "external_id",
    "报告编号": "external_id",
    "单号": "external_id",
    "external_id": "external_id",
    "report_id": "external_id",
    "报告时间": "report_time",
    "出报告时间": "report_time",
    "report_time": "report_time",
    "检查时间": "study_time",
    "拍片时间": "study_time",
    "study_time": "study_time",
    "影像类型": "modality",
    "模态": "modality",
    "患者ID": "patient_id",
    "patient_id": "patient_id",
    "姓名": "patient_name",
    "patient_name": "patient_name",
    "检查单号": "accession_no",
    "accession_no": "accession_no",
    "来源科室": "source_dept",
    "source_dept": "source_dept",
}


def normalize_identifier(value: Optional[str]) -> str:
    """统一检查号/外部ID格式，降低 Excel 数字格式导致的匹配失败。"""
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def normalize_alert_type_text(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def normalize_columns(df: pd.DataFrame) -> dict:
    """标准化列名，返回映射后的数据"""
    records = []
    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            mapped_col = COLUMN_MAPPING.get(col, col)
            value = row[col]
            if pd.notna(value):
                record[mapped_col] = str(value)

        # 检查必填字段: RIS_NO (检查号)
        if "ris_no" not in record or not record.get("ris_no"):
            continue

        record["ris_no"] = normalize_identifier(record.get("ris_no"))
        if not record["ris_no"]:
            continue

        # 组合 report_text = DESCRIPTION + IMPRESSION
        desc = record.get("description", "")
        imp = record.get("impression", "")
        report_text = ""
        if desc:
            report_text += f"【检查所见】\n{desc}\n"
        if imp:
            report_text += f"【诊断意见】\n{imp}"

        # 如果没有 description 和 impression，使用原 report_text
        if not report_text.strip():
            report_text = record.get("report_text", "")

        record["report_text"] = report_text.strip()
        if not record["report_text"]:
            continue

        # 如果没有 external_id，使用 ris_no
        if not record.get("external_id"):
            record["external_id"] = record.get("ris_no")
        else:
            record["external_id"] = normalize_identifier(record.get("external_id"))

        records.append(record)
    return records


# 预标注文件表头映射
PRE_ANNOTATION_COLUMNS = {
    "RIS_NO": "ris_no",
    "CONTENT_TYPE": "content_type",
    "ERR_TYPE": "err_type",
    "SOURCE": "source",
    "TARGET": "target",
    "ALERT_TYPE": "alert_type",
    "ALTER_TYPE": "alert_type",
    "ALERT_MSG": "alert_msg",
    "SOURCE_IN_START": "source_in_start",
    "SOURCE_IN_END": "source_in_end",
    "SOURCE_IN_LENGTH": "source_in_length",
}


def get_row_value(row: pd.Series, *candidate_keys: str):
    """按候选字段名（忽略大小写）读取单元格值。"""
    normalized = {str(k).strip().upper(): row[k] for k in row.index}
    for key in candidate_keys:
        value = normalized.get(key.strip().upper())
        if pd.notna(value):
            return value
    return None


def parse_pre_annotation_file(content: bytes, filename: str) -> dict:
    """解析预标注文件，返回 {ris_no: [annotations]} """
    if filename.lower().endswith('.xlsx'):
        df = pd.read_excel(BytesIO(content))
    elif filename.lower().endswith('.csv'):
        df = pd.read_csv(BytesIO(content))
    else:
        raise ValueError("Unsupported pre-annotation file format")

    if df is None or df.empty:
        return {}

    result = {}
    for _, row in df.iterrows():
        ris_no_value = get_row_value(row, "RIS_NO", "检查号", "external_id", "报告编号")
        ris_no = normalize_identifier(ris_no_value)
        if not ris_no:
            continue

        annotation = {}
        for col, mapped_col in PRE_ANNOTATION_COLUMNS.items():
            value = get_row_value(row, col)
            if pd.notna(value):
                text = str(value).strip()
                if mapped_col == "alert_type":
                    text = normalize_alert_type_text(text)
                annotation[mapped_col] = text

        # 兼容 ALERT_MESSAGE 字段名
        alert_message = get_row_value(row, "ALERT_MESSAGE", "ALERT_MSG", "提示信息")
        if pd.notna(alert_message):
            annotation["alert_message"] = str(alert_message).strip()
            annotation["alert_msg"] = str(alert_message).strip()

        if annotation:
            if ris_no not in result:
                result[ris_no] = []
            result[ris_no].append(annotation)

    return result


@router.post("/import")
def import_reports(
    file: UploadFile = File(...),
    pre_annotation_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """导入报告 Excel/CSV，支持预标注文件"""
    # 创建导入任务
    task = ImportTask(
        file_name=file.filename,
        status=TASK_PENDING,
        created_by=current_user.id
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 解析预标注文件
    pre_annotations_map = {}
    if pre_annotation_file:
        try:
            pre_content = pre_annotation_file.file.read()
            pre_annotations_map = parse_pre_annotation_file(pre_content, pre_annotation_file.filename)
        except Exception as e:
            print(f"Failed to parse pre-annotation file: {e}")

    # 解析文件
    try:
        task.status = TASK_RUNNING
        task.started_at = datetime.utcnow()
        db.commit()

        content = file.file.read()
        df = None

        if file.filename.lower().endswith('.xlsx'):
            df = pd.read_excel(BytesIO(content))
        elif file.filename.lower().endswith('.csv'):
            df = pd.read_csv(BytesIO(content))
        else:
            raise ValueError("Unsupported file format")

        if df is None or df.empty:
            raise ValueError("Empty file")

        # 标准化列名
        records = normalize_columns(df)

        # 原始报告与预标注文件的 RIS_NO 必须一致，避免错配导入
        if pre_annotations_map:
            report_ris_set = {normalize_identifier(item.get("ris_no")) for item in records if item.get("ris_no")}
            pre_ris_set = {normalize_identifier(item) for item in pre_annotations_map.keys() if item}
            missing_in_pre = sorted([ris for ris in report_ris_set - pre_ris_set if ris])
            extra_in_pre = sorted([ris for ris in pre_ris_set - report_ris_set if ris])
            if missing_in_pre or extra_in_pre:
                hints = []
                if missing_in_pre:
                    hints.append(f"原始报告存在但预标注缺失: {', '.join(missing_in_pre[:10])}")
                if extra_in_pre:
                    hints.append(f"预标注存在但原始报告缺失: {', '.join(extra_in_pre[:10])}")
                raise ValueError(f"上传的原始报告与预标注报告 RIS_NO 不匹配。{'；'.join(hints)}")

        task.total_rows = len(records)
        success_count = 0
        failed_count = 0
        errors = []

        for idx, record in enumerate(records):
            try:
                ris_no = normalize_identifier(record.get("ris_no"))
                pre_annotations = pre_annotations_map.get(ris_no, []) if ris_no else []

                # 检查RIS_NO是否已存在，存在则更新，不存在则新增
                existing_report = None
                if ris_no:
                    existing_report = db.query(Report).filter(
                        Report.ris_no == ris_no,
                        Report.is_cancel == False
                    ).first()

                if existing_report:
                    # 更新已存在的报告
                    existing_report.external_id = record.get("external_id")
                    existing_report.report_text = record["report_text"]
                    existing_report.modality = record.get("modality")
                    existing_report.patient_sex = record.get("patient_sex")
                    existing_report.patient_age = record.get("patient_age")
                    existing_report.exam_item = record.get("exam_item")
                    existing_report.exam_mode = record.get("exam_mode")
                    existing_report.exam_group = record.get("exam_group")
                    existing_report.description = record.get("description")
                    existing_report.impression = record.get("impression")
                    existing_report.pre_annotations = pre_annotations if pre_annotations else None
                    existing_report.is_cancel = False
                else:
                    # 新增报告
                    report = Report(
                        external_id=record.get("external_id"),
                        ris_no=ris_no,
                        report_text=record["report_text"],
                        status=STATUS_IMPORTED,
                        is_cancel=False,
                        imported_by=current_user.id,
                        modality=record.get("modality"),
                        patient_sex=record.get("patient_sex"),
                        patient_age=record.get("patient_age"),
                        exam_item=record.get("exam_item"),
                        exam_mode=record.get("exam_mode"),
                        exam_group=record.get("exam_group"),
                        description=record.get("description"),
                        impression=record.get("impression"),
                        pre_annotations=pre_annotations if pre_annotations else None,
                    )
                    db.add(report)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "row": idx + 1,
                    "external_id": record.get("external_id", ""),
                    "reason": str(e),
                    "raw": record
                })

        # 保存错误报告
        error_report_path = None
        if errors:
            upload_dir = "backend/uploads"
            os.makedirs(upload_dir, exist_ok=True)
            error_file = f"{upload_dir}/import_errors_{task.id}.jsonl"
            with open(error_file, 'w', encoding='utf-8') as f:
                for err in errors:
                    f.write(json.dumps(err, ensure_ascii=False) + '\n')
            error_report_path = error_file

        task.status = TASK_SUCCESS
        task.success_rows = success_count
        task.failed_rows = failed_count
        task.error_report_path = error_report_path
        task.finished_at = datetime.utcnow()

    except Exception as e:
        task.status = TASK_FAILED
        task.message = str(e)
        task.finished_at = datetime.utcnow()

    db.commit()
    db.refresh(task)

    return {"task_id": task.id, "status": task.status}


@router.get("/import-tasks/{task_id}", response_model=ImportTaskResponse)
def get_import_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    task = db.query(ImportTask).filter(ImportTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/import-tasks/{task_id}/errors")
def get_import_errors(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    task = db.query(ImportTask).filter(ImportTask.id == task_id).first()
    if not task or not task.error_report_path:
        return []
    if not os.path.exists(task.error_report_path):
        return []
    errors = []
    with open(task.error_report_path, 'r', encoding='utf-8') as f:
        for line in f:
            errors.append(json.loads(line))
    return errors


@router.get("", response_model=ReportListResponse)
def list_reports(
    status: Optional[str] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    query = db.query(Report).filter(Report.is_cancel == False)

    if status:
        query = query.filter(Report.status == status)
    if q:
        query = query.filter(
            (Report.external_id.ilike(f"%{q}%")) |
            (Report.report_text.ilike(f"%{q}%"))
        )

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    # 添加医生信息到返回结果
    result_items = []
    for item in items:
        annotation = db.query(Annotation).filter(Annotation.report_id == item.id).first()
        annotator_id = item.annotator_doctor_id or (annotation.doctor_id if annotation else None)
        item_dict = {
            'id': item.id,
            'external_id': item.external_id,
            'ris_no': item.ris_no,
            'report_text': item.report_text,
            'status': item.status,
            'imported_by': item.imported_by,
            'imported_at': item.imported_at,
            'assigned_doctor_id': item.assigned_doctor_id,
            'assigned_at': item.assigned_at,
            'annotator_doctor_id': annotator_id,
            'reviewer_doctor_id': item.reviewer_doctor_id,
            'review_assigned_at': item.review_assigned_at,
            'reviewed_at': item.reviewed_at,
            'submitted_at': item.submitted_at,
            'modality': item.modality,
            'patient_name': item.patient_name,
            'patient_sex': item.patient_sex,
            'patient_age': item.patient_age,
            'exam_item': item.exam_item,
            'exam_mode': item.exam_mode,
            'exam_group': item.exam_group,
            'description': item.description,
            'impression': item.impression,
            'pre_annotations': item.pre_annotations,
            'doctor_employee_id': None,
            'doctor_username': None,
            'reviewer_employee_id': None,
            'reviewer_username': None,
            'annotation_data': annotation.data if annotation else None,
            'annotation_status': annotation.status if annotation else None,
            'annotation_submitted_at': annotation.submitted_at if annotation else None,
        }
        if annotator_id:
            doctor = db.query(User).filter(User.id == annotator_id, User.is_cancel == False).first()
            if doctor:
                item_dict['doctor_employee_id'] = doctor.employee_id
                item_dict['doctor_username'] = doctor.username
        if item.reviewer_doctor_id:
            reviewer = db.query(User).filter(User.id == item.reviewer_doctor_id, User.is_cancel == False).first()
            if reviewer:
                item_dict['reviewer_employee_id'] = reviewer.employee_id
                item_dict['reviewer_username'] = reviewer.username
        result_items.append(item_dict)

    return ReportListResponse(
        items=result_items,
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    annotation = db.query(Annotation).filter(Annotation.report_id == report.id).first()
    annotator_id = report.annotator_doctor_id or (annotation.doctor_id if annotation else None)
    doctor = None
    reviewer = None
    if annotator_id:
        doctor = db.query(User).filter(User.id == annotator_id, User.is_cancel == False).first()
    if report.reviewer_doctor_id:
        reviewer = db.query(User).filter(User.id == report.reviewer_doctor_id, User.is_cancel == False).first()

    return {
        "id": report.id,
        "external_id": report.external_id,
        "ris_no": report.ris_no,
        "report_text": report.report_text,
        "status": report.status,
        "imported_by": report.imported_by,
        "imported_at": report.imported_at,
        "assigned_doctor_id": report.assigned_doctor_id,
        "assigned_at": report.assigned_at,
        "annotator_doctor_id": annotator_id,
        "reviewer_doctor_id": report.reviewer_doctor_id,
        "review_assigned_at": report.review_assigned_at,
        "reviewed_at": report.reviewed_at,
        "submitted_at": report.submitted_at,
        "modality": report.modality,
        "patient_name": report.patient_name,
        "patient_sex": report.patient_sex,
        "patient_age": report.patient_age,
        "exam_item": report.exam_item,
        "exam_mode": report.exam_mode,
        "exam_group": report.exam_group,
        "description": report.description,
        "impression": report.impression,
        "pre_annotations": report.pre_annotations,
        "doctor_employee_id": doctor.employee_id if doctor else None,
        "doctor_username": doctor.username if doctor else None,
        "reviewer_employee_id": reviewer.employee_id if reviewer else None,
        "reviewer_username": reviewer.username if reviewer else None,
        "annotation_data": annotation.data if annotation else None,
        "annotation_status": annotation.status if annotation else None,
        "annotation_submitted_at": annotation.submitted_at if annotation else None,
    }


@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """删除报告（仅允许删除 IMPORTED 状态的报告）"""
    report = db.query(Report).filter(Report.id == report_id, Report.is_cancel == False).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "IMPORTED":
        raise HTTPException(status_code=400, detail="只能删除未分发的报告")
    report.is_cancel = True
    db.commit()
    return {"ok": True}


@router.post("/assign", response_model=AssignResponse)
def assign_reports(
    request: AssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """分发报告给医生。
    mode=annotation: 首次标注分发
    mode=review: 复核分发（仅已提交报告）
    mode=auto: 优先首次分发，如无可分发项则执行复核分发
    """
    selected_doctor_ids: List[int] = []
    if request.doctor_ids:
        selected_doctor_ids = [int(doctor_id) for doctor_id in request.doctor_ids]
    elif request.doctor_id is not None:
        selected_doctor_ids = [int(request.doctor_id)]

    if not selected_doctor_ids:
        raise HTTPException(status_code=400, detail="至少选择一名医生")

    # 保留传入顺序并去重
    selected_doctor_ids = list(dict.fromkeys(selected_doctor_ids))

    doctors = db.query(User).filter(
        User.id.in_(selected_doctor_ids),
        User.role == "doctor",
        User.enabled == True,
        User.is_cancel == False
    ).all()
    if len(doctors) != len(selected_doctor_ids):
        raise HTTPException(status_code=400, detail="医生不存在或已被禁用")

    mode = str(request.mode or "auto").strip().lower()
    if mode not in {"auto", "annotation", "review"}:
        raise HTTPException(status_code=400, detail="mode 仅支持 auto / annotation / review")

    # 首次标注可分配集合：
    # 1) 待分发（IMPORTED）
    # 2) 已分发（ASSIGNED）且尚无标注记录（允许覆盖分发）
    annotation_query = db.query(Report).outerjoin(
        Annotation, Report.id == Annotation.report_id
    ).filter(
        Report.is_cancel == False,
        or_(
            Report.status == STATUS_IMPORTED,
            and_(Report.status == STATUS_ASSIGNED, Annotation.id.is_(None))
        )
    )

    # 复核可分配集合：仅已提交
    review_query = db.query(Report).filter(
        Report.is_cancel == False,
        Report.status == STATUS_SUBMITTED
    )

    if request.report_ids:
        annotation_query = annotation_query.filter(
            Report.id.in_(request.report_ids),
            Report.status.in_([STATUS_IMPORTED, STATUS_ASSIGNED])
        )
        review_query = review_query.filter(Report.id.in_(request.report_ids))

        # 显式点选首次分发时，若包含已开始编辑/已提交报告，直接阻断并提示
        locked_reports = db.query(Report.id).join(
            Annotation, Report.id == Annotation.report_id
        ).filter(
            Report.is_cancel == False,
            Report.id.in_(request.report_ids),
            Report.status == STATUS_ASSIGNED
        ).all()
        if locked_reports:
            locked_ids = [str(item[0]) for item in locked_reports]
            preview = "、".join(locked_ids[:20])
            if len(locked_ids) > 20:
                preview += "……"
            raise HTTPException(
                status_code=400,
                detail=f"以下报告已开始编辑或已提交，不能二次分发：{preview}"
            )

    annotation_reports = annotation_query.order_by(Report.id.asc()).all()
    review_reports = review_query.order_by(Report.id.asc()).all()

    selected_mode = "annotation"
    reports = []
    if mode == "annotation":
        reports = annotation_reports
    elif mode == "review":
        reports = review_reports
        selected_mode = "review"
    else:
        if annotation_reports:
            reports = annotation_reports
        else:
            reports = review_reports
            selected_mode = "review"

    if not reports:
        return AssignResponse(assigned=0, per_doctor={}, mode=selected_mode)

    per_doctor: dict[str, int] = {str(doctor_id): 0 for doctor_id in selected_doctor_ids}
    now = datetime.utcnow()

    if selected_mode == "annotation":
        for index, report in enumerate(reports):
            doctor_id = selected_doctor_ids[index % len(selected_doctor_ids)]
            report.assigned_doctor_id = doctor_id
            report.assigned_at = now
            report.status = STATUS_ASSIGNED
            report.annotator_doctor_id = doctor_id
            report.reviewer_doctor_id = None
            report.review_assigned_at = None
            report.reviewed_at = None
            per_doctor[str(doctor_id)] += 1
    else:
        start_idx = 0
        impossible_reports: List[str] = []
        for report in reports:
            annotation = db.query(Annotation).filter(Annotation.report_id == report.id).first()
            annotator_id = report.annotator_doctor_id or (annotation.doctor_id if annotation else None) or report.assigned_doctor_id
            chosen_doctor_id = None
            chosen_idx = None
            for offset in range(len(selected_doctor_ids)):
                idx = (start_idx + offset) % len(selected_doctor_ids)
                candidate_doctor_id = selected_doctor_ids[idx]
                if annotator_id and candidate_doctor_id == annotator_id:
                    continue
                chosen_doctor_id = candidate_doctor_id
                chosen_idx = idx
                break
            if chosen_doctor_id is None:
                impossible_reports.append(str(report.id))
                continue

            report.annotator_doctor_id = annotator_id
            report.reviewer_doctor_id = chosen_doctor_id
            report.review_assigned_at = now
            report.reviewed_at = None
            report.assigned_doctor_id = chosen_doctor_id
            report.assigned_at = now
            report.status = STATUS_REVIEW_ASSIGNED
            per_doctor[str(chosen_doctor_id)] += 1
            start_idx = (chosen_idx + 1) % len(selected_doctor_ids)

        if impossible_reports:
            preview = "、".join(impossible_reports[:20])
            if len(impossible_reports) > 20:
                preview += "……"
            raise HTTPException(
                status_code=400,
                detail=f"以下报告无法分配复核（复核人与标注人不能相同）：{preview}"
            )

    db.commit()
    assigned_total = sum(per_doctor.values())
    return AssignResponse(assigned=assigned_total, per_doctor=per_doctor, mode=selected_mode)


# 导出 API 放在 reports 路由中
export_router = APIRouter()


@export_router.get("/annotations")
def export_annotations(
    status: Optional[str] = None,
    format: str = Query("json"),  # json / csv
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """导出标注结果"""
    query = db.query(Report, Annotation, User).outerjoin(
        Annotation, Report.id == Annotation.report_id
    ).outerjoin(
        User, Report.assigned_doctor_id == User.id
    ).filter(Report.is_cancel == False, Report.status.in_([STATUS_SUBMITTED, STATUS_DONE]))

    if status:
        query = query.filter(Report.status == status)

    results = query.all()

    export_data = []
    for report, annotation, doctor in results:
        item = {
            "report_id": report.id,
            "external_id": report.external_id,
            "report_text": report.report_text[:200] + "..." if len(report.report_text) > 200 else report.report_text,
            "status": report.status,
            "assigned_doctor": doctor.username if doctor else None,
            "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        }
        if annotation:
            item.update({
                "no_error": annotation.data.get("no_error", False),
                "error_items": annotation.data.get("error_items", []),
                "note": annotation.data.get("note", ""),
                "annotation_status": annotation.status
            })
        export_data.append(item)

    return export_data


@router.get("/export/all")
def export_all_reports(
    export_mode: str = Query("multi_sheet"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """批量导出报告与标注数据（Excel，与导入格式一致）"""
    if export_mode not in {"multi_sheet", "zip"}:
        raise HTTPException(status_code=400, detail="export_mode 仅支持 multi_sheet 或 zip")

    query = db.query(Report, Annotation, User).outerjoin(
        Annotation, Report.id == Annotation.report_id
    ).outerjoin(
        User, Report.assigned_doctor_id == User.id
    ).filter(Report.is_cancel == False).order_by(Report.id.asc())
    results = query.all()

    def normalize_content_type(value: str) -> str:
        raw = str(value or "").strip().lower()
        if raw in ["description", "desc", "检查所见"]:
            return "description"
        if raw in ["impression", "impress", "诊断意见"]:
            return "impression"
        return "description"

    def infer_alert_type(anchor: dict, suggestion: str, message: str) -> str:
        action = str((anchor or {}).get("action") or "").strip().lower()
        if action == "prompt":
            return "0"
        if action == "delete":
            return "1"
        if action == "replace":
            return "2"

        alert_type = normalize_alert_type_text((anchor or {}).get("alert_type"))
        if alert_type in {"0", "1", "2"}:
            return alert_type
        if str(suggestion or "").strip():
            return "2"
        if any(k in str(message or "") for k in ["删除", "删去", "移除", "不应存在"]):
            return "1"
        return "0"

    report_columns = [
        "RIS_NO", "MODALITY", "PATIENT_SEX", "PATIENT_AGE",
        "EXAM_ITEM", "EXAM_MODE", "EXAM_GROUP", "DESCRIPTION", "IMPRESSION"
    ]
    annotation_columns = [
        "RIS_NO", "CONTENT_TYPE", "ERR_TYPE", "SOURCE", "TARGET",
        "ALERT_TYPE", "ALERT_MSG", "SOURCE_IN_START", "SOURCE_IN_END", "SOURCE_IN_LENGTH"
    ]

    def to_source_length(start, end, fallback="") -> str:
        if fallback is not None and str(fallback).strip() != "":
            return str(fallback)
        if start is not None and end is not None and str(start).lstrip("-").isdigit() and str(end).lstrip("-").isdigit():
            return str(max(0, int(end) - int(start)))
        return ""

    def empty_annotation_row(ris_no: str) -> dict:
        return {
            "RIS_NO": ris_no or "",
            "CONTENT_TYPE": "",
            "ERR_TYPE": "",
            "SOURCE": "",
            "TARGET": "",
            "ALERT_TYPE": "",
            "ALERT_MSG": "",
            "SOURCE_IN_START": "",
            "SOURCE_IN_END": "",
            "SOURCE_IN_LENGTH": "",
        }

    report_rows = []
    original_pre_annotation_rows = []
    final_annotation_rows = []

    for report, annotation, _doctor in results:
        report_rows.append({
            "RIS_NO": report.ris_no or "",
            "MODALITY": report.modality or "",
            "PATIENT_SEX": report.patient_sex or "",
            "PATIENT_AGE": report.patient_age or "",
            "EXAM_ITEM": report.exam_item or "",
            "EXAM_MODE": report.exam_mode or "",
            "EXAM_GROUP": report.exam_group or "",
            "DESCRIPTION": report.description or "",
            "IMPRESSION": report.impression or "",
        })

        # Sheet 2（可选）：上传时的原始预标注
        pre_items = report.pre_annotations or []
        for pre in pre_items:
            source = str(pre.get("source") or "")
            target = str(pre.get("target") or "")
            message = str(pre.get("alert_message") or pre.get("alert_msg") or "")
            start = pre.get("source_in_start")
            end = pre.get("source_in_end")
            start_text = str(start) if start is not None else ""
            end_text = str(end) if end is not None else ""
            raw_alert_type = pre.get("alert_type")
            alert_type = normalize_alert_type_text(raw_alert_type)
            # 原始预标注表要求与上传文件一致，这里不做类型推断映射。
            original_pre_annotation_rows.append({
                "RIS_NO": report.ris_no or "",
                "CONTENT_TYPE": normalize_content_type(pre.get("content_type")),
                "ERR_TYPE": pre.get("err_type") or "",
                "SOURCE": source,
                "TARGET": target,
                "ALERT_TYPE": alert_type,
                "ALERT_MSG": message,
                "SOURCE_IN_START": start_text,
                "SOURCE_IN_END": end_text,
                "SOURCE_IN_LENGTH": to_source_length(start, end, pre.get("source_in_length")),
            })

        # Sheet 3（或无预标注时的 Sheet 2）：人工最终标注
        final_items = []
        if annotation and annotation.data and annotation.data.get("error_items"):
            final_items = annotation.data.get("error_items") or []

        if not final_items:
            final_annotation_rows.append(empty_annotation_row(report.ris_no or ""))
            continue

        for item in final_items:
            anchor = item.get("anchor") or {}
            source = str(item.get("evidence_text") or anchor.get("source") or "")
            target = str(item.get("suggestion") or anchor.get("target") or "")
            message = str(item.get("description") or "")
            start = anchor.get("source_in_start")
            end = anchor.get("source_in_end")
            start_text = str(start) if start is not None else ""
            end_text = str(end) if end is not None else ""
            final_annotation_rows.append({
                "RIS_NO": report.ris_no or "",
                "CONTENT_TYPE": normalize_content_type(anchor.get("content_type") or item.get("location")),
                "ERR_TYPE": item.get("error_type") or "",
                "SOURCE": source,
                "TARGET": target,
                "ALERT_TYPE": infer_alert_type(anchor, target, message),
                "ALERT_MSG": message,
                "SOURCE_IN_START": start_text,
                "SOURCE_IN_END": end_text,
                "SOURCE_IN_LENGTH": to_source_length(start, end),
            })

    output = BytesIO()
    has_original_pre_annotation = len(original_pre_annotation_rows) > 0
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if export_mode == "zip":
        def build_single_sheet_xlsx(rows: list, columns: list, sheet_name: str) -> bytes:
            single_output = BytesIO()
            with pd.ExcelWriter(single_output, engine="openpyxl") as writer:
                pd.DataFrame(rows, columns=columns).to_excel(writer, index=False, sheet_name=sheet_name)
            return single_output.getvalue()

        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(
                "01_original_reports.xlsx",
                build_single_sheet_xlsx(report_rows, report_columns, "原始报告")
            )
            next_index = 2
            if has_original_pre_annotation:
                zip_file.writestr(
                    f"{next_index:02d}_original_pre_annotations.xlsx",
                    build_single_sheet_xlsx(original_pre_annotation_rows, annotation_columns, "原始预标注")
                )
                next_index += 1
            zip_file.writestr(
                f"{next_index:02d}_final_annotations.xlsx",
                build_single_sheet_xlsx(final_annotation_rows, annotation_columns, "标注结果")
            )
        filename = f"annotated_reports_{timestamp}.zip"
        media_type = "application/zip"
    else:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame(report_rows, columns=report_columns).to_excel(writer, index=False, sheet_name="原始报告")
            if has_original_pre_annotation:
                pd.DataFrame(original_pre_annotation_rows, columns=annotation_columns).to_excel(
                    writer, index=False, sheet_name="原始预标注"
                )
            pd.DataFrame(final_annotation_rows, columns=annotation_columns).to_excel(
                writer, index=False, sheet_name="标注结果"
            )
        filename = f"annotated_reports_{timestamp}.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return Response(
        content=output.getvalue(),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# 注册导出路由
router.include_router(export_router, prefix="")
