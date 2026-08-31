/* Client-side routing on a bucket, done at the edge instead of in an error page.
 *
 * S3 has no notion of /projects/foo, so something has to turn that request into
 * a request for index.html and let the shell's own router read the path. The
 * usual trick is a CloudFront custom error response mapping 403 and 404 to
 * /index.html at 200 -- but custom error responses apply to the whole
 * distribution, not to one behaviour, so they also catch the API's 404s. A
 * request for a post that does not exist would come back as index.html with a
 * 200, the shell would try to parse the HTML as JSON, and a missing page would
 * report itself as "something went wrong" instead of "not found".
 *
 * Rewriting here keeps the two apart: this runs on the default behaviour only,
 * so /api/* passes through with whatever status the API gave it.
 *
 * The test is "does the last path segment have a dot in it". Files have
 * extensions and routes do not, which is true of every path this site serves --
 * the assets are /static/css/style.min.css and the routes are /projects/foo.
 */
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  var last = uri.substring(uri.lastIndexOf("/") + 1);

  if (last.indexOf(".") === -1) {
    request.uri = "/index.html";
  }

  return request;
}
