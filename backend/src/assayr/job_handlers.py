"""Import every module that registers a job handler (used by the worker and tests)."""

import assayr.scoring.jobs  # noqa: F401
import assayr.training.jobs  # noqa: F401
import assayr.verification.engine  # noqa: F401
