"""中文友好的粗略 token 估算：上下文裁剪与历史预算共用同一把尺。"""


def estimate_tokens(text: str) -> int:
    chinese_chars = sum(1 for char in text if "一" <= char <= "鿿")
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)
