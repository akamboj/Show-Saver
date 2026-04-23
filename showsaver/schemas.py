from marshmallow import Schema, fields


class ErrorSchema(Schema):
    success = fields.Boolean()
    message = fields.String()


# --- /submit ---
class SubmitRequestSchema(Schema):
    text = fields.String(required=True, metadata={'description': 'URL to download'})


class SubmitResponseSchema(Schema):
    success = fields.Boolean()
    message = fields.String()
    job_id = fields.String()
    url = fields.String()
    queue_position = fields.Integer()
    status = fields.String()


# --- /status/<job_id> and /queue
class JobStatusSchema(Schema):
    id = fields.String()
    url = fields.String()
    status = fields.String()
    queued_at = fields.String()
    progress = fields.Integer()
    step = fields.Integer()
    step_type = fields.String()
    total_steps = fields.Integer()
    started_at = fields.String()
    completed_at = fields.String()
    error = fields.String()
    file_path = fields.String()
    size = fields.Integer()


class StatusResponseSchema(Schema):
    success = fields.Boolean()
    status = fields.Nested(JobStatusSchema)


class QueueResponseSchema(Schema):
    success = fields.Boolean()
    queued = fields.List(fields.Nested(JobStatusSchema))
    downloading = fields.List(fields.Nested(JobStatusSchema))
    completed = fields.List(fields.Nested(JobStatusSchema))
    queue_size = fields.Integer()
    total_queue_size = fields.Integer()


# --- /history ---
class HistoryResponseSchema(Schema):
    status = fields.String()


# -- /dropout/new-releases
class DropoutVideoSchema(Schema):
    id = fields.Integer()
    title = fields.String()
    url = fields.String()
    thumbnail = fields.String()
    duration = fields.Integer()
    show_name = fields.String()


class NewReleasesQuerySchema(Schema):
    refresh = fields.Boolean(required=False, load_default=False)


class NewReleasesResponseSchema(Schema):
    success = fields.Boolean()
    videos = fields.List(fields.Nested(DropoutVideoSchema))
    count = fields.Integer()
    cached = fields.Boolean()


# --- /dropout/info
class EpisodeInfoQuerySchema(Schema):
    episode = fields.String(required=True)


class DropoutEpisodeInfoSchema(Schema):
    url_path = fields.String()
    url = fields.String()
    show_name = fields.String(allow_none=True)
    title = fields.String(allow_none=True)
    thumbnail = fields.String(allow_none=True)
    duration = fields.Integer(allow_none=True)
    fetched_at = fields.Float(allow_none=True)


class EpisodeInfoResponseSchema(Schema):
    success = fields.Boolean()
    info = fields.Nested(DropoutEpisodeInfoSchema, allow_none=True)
