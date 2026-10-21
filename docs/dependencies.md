# Dependency decisions

The initial environment targets Python 3.11 on Windows x64. Exact resolved versions
belong in `requirements-lock.txt` after installation and verification. The lock
describes the core tools, not an approved model checkpoint.

| Dependency | License / source | Decision |
|---|---|---|
| Python | PSF; https://docs.python.org/3/license.html | Local runtime |
| uv | MIT or Apache-2.0; https://docs.astral.sh/uv/reference/policies/license/ | Environment bootstrap only |
| NumPy | BSD-3-Clause; https://numpy.org/doc/stable/license.html | Geometry and arrays |
| OpenCV | Apache-2.0 for current OpenCV; https://opencv.org/license/ | Video, polygon geometry, manual calibration |
| SQLAlchemy | MIT; https://www.sqlalchemy.org/download.html | Synchronous PostgreSQL access |
| Alembic | MIT; https://github.com/sqlalchemy/alembic/blob/main/LICENSE | Schema migrations |
| psycopg | LGPL-3.0; https://www.psycopg.org/license/ | PostgreSQL driver; binary distribution includes additional notices |
| PyYAML | MIT; https://github.com/yaml/pyyaml/blob/main/LICENSE | Experiment configuration |
| pytest | MIT; https://docs.pytest.org/en/stable/license.html | Tests |
| Ruff | MIT; https://github.com/astral-sh/ruff/blob/main/LICENSE | Formatting and static checks |
| PyTorch | BSD-style; https://github.com/pytorch/pytorch/blob/main/LICENSE | Optional GPU diagnostic; separate installation |
| PostgreSQL | PostgreSQL License; https://www.postgresql.org/about/licence/ | Portable local instance / Compose |
| Ultralytics | AGPL-3.0 / Enterprise; https://www.ultralytics.com/license | Pending code and checkpoint usage decision; excluded from core installation |

Do not assume a library license grants rights to its pretrained weights or datasets.
Before distribution, review installed wheel notices and bundled/transitive libraries
(particularly OpenCV video codecs and psycopg binary libraries). This table is an
engineering inventory, not clearance for a future proprietary product. No project
license has been selected.
