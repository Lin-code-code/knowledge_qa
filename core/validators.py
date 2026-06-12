def validate_file_extension(filename: str, allowed_types: set[str]) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in allowed_types:
        raise ValueError(
            f"不支持的文件类型: {extension or 'unknown'}，仅支持: {sorted(allowed_types)}"
        )
    return extension
