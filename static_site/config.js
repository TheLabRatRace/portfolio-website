// The one line the deploy rewrites. sync_static.sh substitutes __API_BASE__;
// left alone, the token is not a valid path and the shell falls back to
// /api/v1, which is what tools/serve_shell.py serves locally.
//
// Same-origin by default, and that is the arrangement that works: the
// distribution serves this shell from S3 and forwards /api/* to the ECS task,
// so the fetches are same-origin -- no CORS preflight, and no https page
// trying to call a plain-http backend.
(function () {
  var base = "__API_BASE__";
  window.SITE = { apiBase: base.indexOf("_") === 0 ? "/api/v1" : base };
})();
