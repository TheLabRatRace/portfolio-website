from flask_wtf.csrf import CSRFProtect

# Every POST in the admin carries a token. This is the one protection that
# cannot be added later per-form and be trusted -- it has to be global, so a
# form added next year is covered by default rather than by remembering.
csrf = CSRFProtect()
