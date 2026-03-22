class Processor:
    def process_info_dict(self, info_dict):
        pass

    def process_dlp_opts(self, dlp_opts, info_dict):
        pass

    def process_show_name(self, show_name) -> str:
        return show_name

    def should_trigger_rename(self, info_dict) -> bool:
        return False
