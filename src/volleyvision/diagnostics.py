"""Environment diagnostics without fetching models or calling remote services."""

import platform
from importlib.metadata import PackageNotFoundError, version


def environment_report() -> dict:
    result = {"python": platform.python_version(), "platform": platform.system(), "packages": {}}
    for package in (
        "numpy",
        "opencv-python",
        "SQLAlchemy",
        "alembic",
        "psycopg",
        "torch",
        "torchvision",
        "ultralytics",
    ):
        try:
            result["packages"][package] = version(package)
        except PackageNotFoundError:
            result["packages"][package] = None
    try:
        import torch
    except ImportError:
        result["cuda"] = {"available": False, "reason": "PyTorch is not installed"}
        return result
    available = torch.cuda.is_available()
    result["cuda"] = {"available": available, "build": torch.version.cuda}
    if available:
        sample = torch.ones((32, 32), device="cuda")
        assert (sample @ sample).sum().item() == 32768
        torch.cuda.synchronize()
        result["cuda"].update(
            name=torch.cuda.get_device_name(0),
            capability=list(torch.cuda.get_device_capability(0)),
            tensor_smoke="passed",
        )
    return result
