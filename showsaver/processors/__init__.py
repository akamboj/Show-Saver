class Processor:
    def process_info_dict(self, info_dict) -> None:
        pass

    def process_dlp_opts(self, dlp_opts, info_dict) -> None:
        pass

    def process_show_name(self, show_name: str) -> str:
        return show_name

    def should_trigger_rename(self, info_dict) -> bool:
        return False

    def find_corrected_url(self, show_url: str, info_dict) -> tuple[str, dict] | None:
        return None
