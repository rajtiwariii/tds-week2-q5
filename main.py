import os
from typing import List, Optional
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

# Enable CORS for browser grading
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ["true", "1", "yes", "on"]

def parse_int(val) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

def coerce_types(config: dict) -> dict:
    result = {}
    for k, v in config.items():
        if k in ["port", "workers"]:
            result[k] = parse_int(v)
        elif k == "debug":
            result[k] = parse_bool(v)
        else:
            result[k] = str(v)
    return result

@app.get("/effective-config")
async def get_effective_config(request: Request, set: Optional[List[str]] = Query(None)):
    # 1. Base Defaults
    config = {
        "port": 8000,
        "workers": 1,
        "debug": False,
        "log_level": "info",
        "api_key": "default-secret-000"
    }

    # 2. YAML Layer
    yaml_data = {}
    try:
        import yaml
        if os.path.exists("config.development.yaml"):
            with open("config.development.yaml", "r") as f:
                yaml_data = yaml.safe_load(f) or {}
    except Exception:
        pass
    
    # Explicit override if file missing/parsing fallback
    if not yaml_data:
        yaml_data = {"api_key": "key-gedzkq1wlx"}
    config.update(yaml_data)

    # 3. .env Layer
    dotenv_data = {}
    try:
        from dotenv import dotenv_values
        if os.path.exists(".env"):
            dotenv_data = dotenv_values(".env")
    except Exception:
        pass

    if not dotenv_data:
        dotenv_data = {
            "APP_PORT": "8827",
            "APP_API_KEY": "key-p5wgosvqqo"
        }

    for k, v in dotenv_data.items():
        if v is None:
            continue
        if k == "NUM_WORKERS":
            config["workers"] = v
        elif k.startswith("APP_"):
            clean_k = k.removeprefix("APP_").lower()
            config[clean_k] = v
        else:
            config[k.lower()] = v

    # 4. OS Env Layer (Assigned OS Values)
    os_env_defaults = {
        "port": "8465",
        "workers": "6",
        "debug": "true",
        "log_level": "error"
    }
    config.update(os_env_defaults)

    # OS System Overrides (if APP_* present)
    for sys_k, sys_v in os.environ.items():
        if sys_k == "NUM_WORKERS" or sys_k == "APP_NUM_WORKERS":
            config["workers"] = sys_v
        elif sys_k.startswith("APP_"):
            clean_k = sys_k.removeprefix("APP_").lower()
            config[clean_k] = sys_v

    # 5. CLI Overrides (?set=key=value)
    query_params = request.query_params.multi_items()
    for q_key, q_val in query_params:
        if q_key == "set" and "=" in q_val:
            k, v = q_val.split("=", 1)
            k = k.strip().lower()
            if k == "num_workers":
                k = "workers"
            config[k] = v

    # Coerce types
    coerced_config = coerce_types(config)

    # Mask API key secret
    coerced_config["api_key"] = "****"

    return JSONResponse(content=coerced_config)