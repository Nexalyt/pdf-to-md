import uuid
import os
import uvicorn
import click
import sentry_sdk
from pathlib import Path
from glob import glob
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from loguru import logger
from base64 import b64encode

from mineru.cli.common import aio_do_parse, read_fn, pdf_suffixes, image_suffixes
from mineru.utils.cli_parser import arg_parse
from mineru.version import __version__

# Initialize Sentry SDK before creating FastAPI app
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", "https://99d06b36f4d6e2507646f4ee49237bd8@o4509698369257472.ingest.us.sentry.io/4509698396127232"),
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Set profile_session_sample_rate to 1.0 to profile 100%
    # of profile sessions.
    profile_session_sample_rate=1.0,
    # Set profile_lifecycle to "trace" to automatically
    # run the profiler on when there is an active transaction
    profile_lifecycle="trace",
    environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
)

app = FastAPI(
    title="MinerU API",
    description="PDF to Markdown conversion API with ML models",
    version="2.0.0"
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add Sentry debug endpoint for verification
@app.get("/sentry-debug")
async def trigger_error():
    """Endpoint to test Sentry error tracking"""
    division_by_zero = 1 / 0

# Add health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "mineru-api", "version": __version__}

def encode_image(image_path: str) -> str:
    """Encode image using base64"""
    with open(image_path, "rb") as f:
        return b64encode(f.read()).decode()


def get_infer_result(file_suffix_identifier: str, pdf_name: str, parse_dir: str) -> Optional[str]:
    """从结果文件中读取推理结果 | en: Read inference results from the result file"""
    result_file_path = os.path.join(parse_dir, f"{pdf_name}{file_suffix_identifier}")
    if os.path.exists(result_file_path):
        with open(result_file_path, "r", encoding="utf-8") as fp:
            return fp.read()
    return None


@app.post(path="/file_parse",)
async def parse_pdf(
        files: List[UploadFile] = File(...),
        output_dir: str = Form("./output"),
        lang_list: List[str] = Form(["ch"]),
        backend: str = Form("pipeline"),
        parse_method: str = Form("auto"),
        formula_enable: bool = Form(True),
        table_enable: bool = Form(True),
        server_url: Optional[str] = Form(None),
        return_md: bool = Form(True),
        return_middle_json: bool = Form(False),
        return_model_output: bool = Form(False),
        return_content_list: bool = Form(False),
        return_images: bool = Form(False),
        start_page_id: int = Form(0),
        end_page_id: int = Form(99999),
):

    # 获取命令行配置参数 | en: Get command line configuration parameters
    config = getattr(app.state, "config", {})

    try:
        # Add Sentry context for better error tracking and debugging
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("backend", backend)
            scope.set_tag("parse_method", parse_method)
            scope.set_context("files", {
                "count": len(files),
                "names": [f.filename for f in files]
            })
            scope.set_context("config", {
                "lang_list": lang_list,
                "formula_enable": formula_enable,
                "table_enable": table_enable,
            })

        # 创建唯一的输出目录 | en: Create a unique output directory
        unique_dir = os.path.join(output_dir, str(uuid.uuid4()))
        os.makedirs(unique_dir, exist_ok=True)

        # 处理上传的PDF文件 | en: Process uploaded PDF files
        pdf_file_names = []
        pdf_bytes_list = []

        for file in files:
            content = await file.read()
            file_path = Path(file.filename)

            if file_path.suffix.lower() not in pdf_suffixes + image_suffixes:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Unsupported file type: {file_path.suffix}"}
                )


            # 创建临时文件以便使用read_fn | en: Create a temporary file for read_fn
            temp_path = Path(unique_dir) / file_path.name
            with open(temp_path, "wb") as f:
                f.write(content)

            try:
                pdf_bytes = read_fn(temp_path)
                pdf_bytes_list.append(pdf_bytes)
                pdf_file_names.append(file_path.stem)
                os.remove(temp_path)  # 删除临时文件 | en: Remove temporary file after reading
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Failed to load file: {str(e)}"}
                )
        # 设置语言列表，确保与文件数量一致 | en: Set language list to match the number of files
        actual_lang_list = lang_list
        if len(actual_lang_list) != len(pdf_file_names):
            # 如果语言列表长度不匹配，使用第一个语言或默认"ch" | en: If the language list length does not match, use the first language or default to "ch"
            actual_lang_list = [actual_lang_list[0] if actual_lang_list else "ch"] * len(pdf_file_names)

        # 调用异步处理函数 | en: Call the asynchronous processing function
        await aio_do_parse(
            output_dir=unique_dir,
            pdf_file_names=pdf_file_names,
            pdf_bytes_list=pdf_bytes_list,
            p_lang_list=actual_lang_list,
            backend=backend,
            parse_method=parse_method,
            formula_enable=formula_enable,
            table_enable=table_enable,
            server_url=server_url,
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_md=return_md,
            f_dump_middle_json=return_middle_json,
            f_dump_model_output=return_model_output,
            f_dump_orig_pdf=False,
            f_dump_content_list=return_content_list,
            start_page_id=start_page_id,
            end_page_id=end_page_id,
            **config
        )

        # ch:构建结果路径 | en: Build result paths
        result_dict = {}
        for pdf_name in pdf_file_names:
            result_dict[pdf_name] = {}
            data = result_dict[pdf_name]

            if backend.startswith("pipeline"):
                parse_dir = os.path.join(unique_dir, pdf_name, parse_method)
            else:
                parse_dir = os.path.join(unique_dir, pdf_name, "vlm")

            if os.path.exists(parse_dir):
                if return_md:
                    data["md_content"] = get_infer_result(".md", pdf_name, parse_dir)
                if return_middle_json:
                    data["middle_json"] = get_infer_result("_middle.json", pdf_name, parse_dir)
                if return_model_output:
                    if backend.startswith("pipeline"):
                        data["model_output"] = get_infer_result("_model.json", pdf_name, parse_dir)
                    else:
                        data["model_output"] = get_infer_result("_model_output.txt", pdf_name, parse_dir)
                if return_content_list:
                    data["content_list"] = get_infer_result("_content_list.json", pdf_name, parse_dir)
                if return_images:
                    image_paths = glob(f"{parse_dir}/images/*.jpg")
                    data["images"] = {
                        os.path.basename(
                            image_path
                        ): f"data:image/jpeg;base64,{encode_image(image_path)}"
                        for image_path in image_paths
                    }
        return JSONResponse(
            status_code=200,
            content={
                "backend": backend,
                "version": __version__,
                "results": result_dict
            }
        )
    except Exception as e:
        # Sentry will automatically capture this exception
        sentry_sdk.capture_exception(e)
        logger.exception(e)
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Failed to process file: {str(e)}",
                "request_id": str(uuid.uuid4())
            }
        )


@click.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.pass_context
@click.option('--host', default='127.0.0.1', help='Server host (default: 127.0.0.1)')
@click.option('--port', default=8000, type=int, help='Server port (default: 8000)')
@click.option('--reload', is_flag=True, help='Enable auto-reload (development mode)')
def main(ctx, host, port, reload, **kwargs):

    kwargs |= arg_parse(ctx)

    # 将配置参数存储到应用状态中
    app.state.config = kwargs

    """启动MinerU FastAPI服务器的命令行入口"""
    print(f"Start MinerU FastAPI Service: http://{host}:{port}")
    print("The API documentation can be accessed at the following address:")
    print(f"- Swagger UI: http://{host}:{port}/docs")
    print(f"- ReDoc: http://{host}:{port}/redoc")
    print(f"- Sentry Debug: http://{host}:{port}/sentry-debug")
    print(f"- Health Check: http://{host}:{port}/health")

    uvicorn.run(
        "mineru.cli.fast_api:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    main()