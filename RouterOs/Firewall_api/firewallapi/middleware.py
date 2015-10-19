# yes
import simplejson as json
import logging

from lxml import etree
import webob

from firewallapi.common import utils


LOG = logging.getLogger(__name__)


class ParsableErrorMiddleware(object):
    """Replace error body with something the client can parse."""

    @staticmethod
    def best_match_language(accept_language):
        """Determines best available locale from the Accept-Language header.

        :returns: the best language match or None if the 'Accept-Language'
                  header was not available in the request.
        """
        if not accept_language:
            return None
        all_languages = utils.get_available_languages('firewallapi')
        return accept_language.best_match(all_languages)

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Request for this state, modified by replace_start_response()
        # and used when an error is being reported.
        state = {}

        def replacement_start_response(status, headers, exc_info=None):
            """Overrides the default response to make errors parsable."""
            try:
                status_code = int(status.split(' ')[0])
                state['status_code'] = status_code
            except (ValueError, TypeError):  # pragma: nocover
                raise Exception((
                    'ErrorDocumentMiddleware received an invalid '
                    'status %s' % status
                ))
            else:
                if (state['status_code'] / 100) not in (2, 3):
                    # Remove some headers so we can replace them later
                    # when we have the full error message and can
                    # compute the length.
                    headers = [(h, v)
                               for (h, v) in headers
                               if h not in ('Content-Length', 'Content-Type')
                               ]
                # Save the headers in case we need to modify them.
                state['headers'] = headers
                return start_response(status, headers, exc_info)

        appiter = self.app(environ, replacement_start_response)
        app_iter = self.format_exception(appiter)

        if (state['status_code'] / 100) not in (2, 3):
            req = webob.Request(environ)
            error = None
            user_locale = self.best_match_language(req.accept_language)
            if (req.accept.best_match(['application/json', 'application/xml'])
               == 'application/xml'):
                try:
                    # simple check xml is valid
                    fault = etree.fromstring('\n'.join(app_iter))
                    # Add the translated error to the xml data
                    if error is not None:
                        for fault_string in fault.findall('faultstring'):
                            fault_string.text = (
                                utils.translate(
                                    error, user_locale))
                    body = ['<error_message>' + etree.tostring(fault)
                            + '</error_message>']
                except etree.XMLSyntaxError as err:
                    LOG.error('Error parsing HTTP response: %s' % err)
                    body = ['<error_message>%s' % state['status_code']
                            + '</error_message>']
                state['headers'].append(('Content-Type', 'application/xml'))
            else:
                try:
                    fault = json.loads('\n'.join(app_iter))
                    if error is not None and 'faultstring' in fault:
                        fault['faultstring'] = (
                            utils.translate(
                                error, user_locale))
                    body = [json.dumps({'error_message': fault})]
                except ValueError as err:
                    body = [json.dumps({'error_message': '\n'.join(app_iter)})]
                state['headers'].append(('Content-Type', 'application/json'))
            state['headers'].append(('Content-Length', str(len(body[0]))))
        else:
            body = app_iter
        return body

    def format_exception(self, excinfo):
        app_result = []
        src_excinfo = excinfo
        try:
            if excinfo and len(excinfo) == 1:
                exc_info = json.loads(excinfo[0])
                exc_faultstring = json.loads(exc_info.pop('faultstring'))
                error_msg = dict(
                    debuginfo=unicode(exc_info['debuginfo']),
                    faultcode=unicode(exc_faultstring['faultcode']),
                    faultstring=unicode(exc_faultstring['msg']))

                error_msg = json.dumps(error_msg)
                app_result.append(error_msg)
                return app_result
            else:
                return src_excinfo
        except Exception:
            return src_excinfo
