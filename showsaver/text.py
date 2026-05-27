FULLWIDTH_DOUBLE_QUOTE = '\uff02'


def normalize_title(title: str) -> str:
    title = title.replace(FULLWIDTH_DOUBLE_QUOTE, '\'')
    title = title.replace("\"", '\'')
    return title
