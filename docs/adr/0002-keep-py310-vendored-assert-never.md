# Keep Python 3.10, with a vendored `_assert_never`

`requires-python` floors at `>=3.10` and CI runs the matrix from 3.10 to 3.14t, so the exhaustive
`match` over `_EofAction` in `fixer.py` cannot use `typing.assert_never`, which is 3.11+, and
`typing_extensions` would become a new direct dependency. The original plan leaned on the return
type and was dropped: `fix_file` is typed `-> bool`, so a lost `match` arm falls through to an
implicit `None` that ty already rejects, but the error surfaces on the return type not the `match`,
and it vanishes for any future consumer of `_EofAction` that legitimately returns `None`. The
two-line vendored `_assert_never(value: NoReturn) -> NoReturn` pins the error at the `case _:` arm
on every supported version for no dependency, and dropping 3.10 to save it would be an
outward-facing breaking change. Python 3.10 reaches end of life on 2026-10-31, which is when the
floor moves to 3.11 and the helper becomes `from typing import assert_never`.
