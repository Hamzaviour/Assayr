"""Import every module that registers a job handler (used by the worker and tests)."""

import assayr.mail.jobs  # noqa: F401
import assayr.models  # noqa: F401  (every table, so the worker's flushes can resolve all foreign keys)
import assayr.scoring.jobs  # noqa: F401
import assayr.training.jobs  # noqa: F401
import assayr.verification.engine  # noqa: F401
