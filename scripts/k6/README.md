# k6 压测

## 1. 目标

`admin_read_load.js` 用于压测后台常见接口：
- 登录 `/api/auth/login`
- 健康检查 `/api/health`
- 管理端报告列表 `/api/reports`
- 管理端报告详情 `/api/reports/{id}`
- 医生账号列表 `/api/users?role=doctor`
- 医生端报告列表 `/api/doctor/reports`
- 可选：全量导出 `/api/reports/export/all`

## 2. 前置条件

- 后端服务可访问（默认：`http://127.0.0.1:8088`）
- 存在可登录管理员账号（默认：`admin/admin123`）

## 3. 运行方式

### 方式 A：本机安装 k6

```bash
k6 run scripts/k6/admin_read_load.js \
  -e BASE_URL=http://127.0.0.1:8088 \
  -e USERNAME=admin \
  -e PASSWORD=admin123
```

### 方式 B：Docker 运行 k6（未安装 k6 时）

```bash
docker run --rm -i -v "$PWD:/work" -w /work grafana/k6 run scripts/k6/admin_read_load.js \
  -e BASE_URL=http://host.docker.internal:8088 \
  -e USERNAME=admin \
  -e PASSWORD=admin123
```

> Linux 如使用 Docker，可把 `BASE_URL` 改为宿主机可达地址（例如网卡 IP）。

## 4. 常用参数

- `STAGES`：`持续时间:目标VU`，逗号分隔
  - 默认：`30s:5,2m:20,30s:0`
  - 示例：`-e STAGES="1m:20,3m:50,1m:0"`
- `START_VUS`：起始 VU（默认 `1`）
- `THINK_TIME`：每轮请求后停顿秒数（默认 `0.2`）
- `REPORT_PAGE_SIZE`：报告列表分页大小（默认 `20`）
- `REPORT_STATUS`：只测某个状态（如 `IMPORTED`）
- `REPORT_QUERY`：只测某个搜索关键词

## 5. 导出接口压测（可选）

导出接口开销很大，建议单独开启：

```bash
k6 run scripts/k6/admin_read_load.js \
  -e BASE_URL=http://127.0.0.1:8088 \
  -e USERNAME=admin \
  -e PASSWORD=admin123 \
  -e INCLUDE_EXPORT=true \
  -e EXPORT_MODE=multi_sheet \
  -e EXPORT_RATE=1 \
  -e EXPORT_DURATION=2m
```

参数说明：
- `INCLUDE_EXPORT=true`：启用导出场景
- `EXPORT_MODE`：`multi_sheet` 或 `zip`
- `EXPORT_RATE`：每分钟触发次数（默认 `1`）
- `EXPORT_DURATION`：持续时间（默认 `2m`）
- `EXPORT_PRE_VUS` / `EXPORT_MAX_VUS`：导出场景的 VU 配置
- `EXPORT_TIMEOUT`：导出请求超时（默认 `180s`）

## 6. 导出压测报告

```bash
k6 run scripts/k6/admin_read_load.js \
  -e BASE_URL=http://127.0.0.1:8088 \
  --summary-export=/tmp/k6-summary.json
```

## 7. 医院科室 50+ 并发脚本

脚本：`scripts/k6/hospital_department_50plus.js`

特点：
- 面向医生并发主场景（默认目标并发 `60`）
- 每个 VU 绑定医生账号并执行：医生列表 -> 抽样详情 -> 可选草稿保存
- 可选并发管理员探针（报告列表、医生列表）

### 7.1 最简单（单医生账号，仅用于服务压测）

```bash
k6 run scripts/k6/hospital_department_50plus.js \
  -e BASE_URL=http://127.0.0.1:8088 \
  -e DOCTOR_USERNAME=doctor1 \
  -e DOCTOR_PASSWORD=doctor123 \
  -e TARGET_VUS=60 \
  -e RAMP_UP=5m \
  -e STEADY=20m \
  -e RAMP_DOWN=5m
```

### 7.2 推荐（账号池，模拟科室多人）

优先推荐使用账号文件，避免 shell 引号或历史环境变量干扰：

```bash
env -u DOCTOR_USER_PREFIX -u DOCTOR_USER_START -u DOCTOR_USER_END -u DOCTOR_USER_PAD -u DOCTOR_USERNAME -u DOCTOR_PASSWORD \
k6 run scripts/k6/hospital_department_50plus.js \
  -e BASE_URL=http://127.0.0.1:8088 \
  -e DOCTOR_CREDENTIALS_FILE="$PWD/scripts/k6/doctor_credentials.hospital.json" \
  -e TARGET_VUS=50 \
  -e RAMP_UP=2m \
  -e STEADY=10m \
  -e RAMP_DOWN=2m
```

可通过前缀批量生成账号：

```bash
k6 run scripts/k6/hospital_department_50plus.js \
  -e BASE_URL=http://127.0.0.1:8088 \
  -e DOCTOR_USER_PREFIX=doc_ \
  -e DOCTOR_USER_START=1 \
  -e DOCTOR_USER_END=80 \
  -e DOCTOR_USER_PAD=3 \
  -e DOCTOR_PASSWORD=doctor123 \
  -e TARGET_VUS=60
```

也可直接传 JSON：

```bash
DOCTOR_CREDENTIALS_JSON="$(cat scripts/k6/doctor_credentials.example.json)" \
k6 run scripts/k6/hospital_department_50plus.js \
  -e BASE_URL=http://127.0.0.1:8088 \
  -e DOCTOR_CREDENTIALS_JSON="$DOCTOR_CREDENTIALS_JSON" \
  -e TARGET_VUS=60
```

脚本启动时会打印账号来源日志，例如：

```text
doctor credentials mode selected=file, configured=file,prefix, total=7, targetVUs=50, unique=false
multiple doctor credential modes detected; precedence is file > json > single > prefix
```

### 7.3 可选写入流量（草稿保存）

默认关闭写接口。打开方式：

```bash
k6 run scripts/k6/hospital_department_50plus.js \
  -e BASE_URL=http://127.0.0.1:8088 \
  -e DOCTOR_USER_PREFIX=doc_ \
  -e DOCTOR_USER_START=1 \
  -e DOCTOR_USER_END=80 \
  -e DOCTOR_PASSWORD=doctor123 \
  -e ENABLE_DRAFT_WRITE=true \
  -e DRAFT_RATIO=0.15
```

> 建议在测试环境启用写入，避免污染生产数据。
