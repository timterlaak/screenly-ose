import requests
import json
import re
from netifaces import ifaddresses, AF_INET, AF_LINK
from sh import grep, netstat
from urlparse import urlparse
from datetime import timedelta
from settings import settings
import socket

# This will only work on the Raspberry Pi,
# so let's wrap it in a try/except so that
# Travis can run.
try:
    from sh import omxplayer
except:
    pass


def validate_url(string):
    """Simple URL verification.

    >>> validate_url("hello")
    False
    >>> validate_url("ftp://example.com")
    False
    >>> validate_url("http://")
    False
    >>> validate_url("http://wireload.net/logo.png")
    True
    >>> validate_url("https://wireload.net/logo.png")
    True

    """

    checker = urlparse(string)
    return bool(checker.scheme in ('rtsp', 'rtmp', 'http', 'https') and checker.netloc)


def get_node_ip():
    """Returns the node's IP and MAC address, for the interface
    that is being used as the default gateway.
    This shuld work on both MacOS X and Linux."""

    try:
        default_interface = grep(netstat('-nr'), '-e', '^default', '-e' '^0.0.0.0').split()[-1]
        #my_ip = ifaddresses(default_interface)[2][0]['addr']
        my_ip = ifaddresses(default_interface)[AF_INET][0]['addr']
        my_mac = ifaddresses(default_interface)[AF_LINK][0]['addr']
        return (my_ip, my_mac)
        #return my_ip
    except:
        pass

    return (None, None)


def get_video_duration(file):
    """
    Returns the duration of a video file in timedelta.
    """
    time = None
    try:
        run_omxplayer = omxplayer(file, info=True, _err_to_out=True)
        for line in run_omxplayer.split('\n'):
            if 'Duration' in line:
                match = re.search(r'[0-9]+:[0-9]+:[0-9]+\.[0-9]+', line)
                if match:
                    time_input = match.group()
                    time_split = time_input.split(':')
                    hours = int(time_split[0])
                    minutes = int(time_split[1])
                    seconds = float(time_split[2])
                    time = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                break
    except:
        pass

    return time


def handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError('Object of type %s with value of %s is not JSON serializable' % (type(obj), repr(obj)))


def json_dump(obj):
    return json.dumps(obj, default=handler)


def url_fails(url):
    """
    Accept 200 and 405 as 'OK' statuses for URLs.
    Some hosting providers (like Google App Engine) throws a 405 at `requests`.
    Can not check RTSP or RTMP, so we just believe it is there (if not OMX Player will terminate, and the next asset is shown -> no ugly error messages)
    """
    if url.startswith('rtsp://'):
	return False
    if url.startswith('rtmp://'):
        return False
    try:
        if validate_url(url):
            obj = requests.head(url, allow_redirects=True, timeout=10, verify=settings['verify_ssl'])
            assert obj.status_code in (200, 405)
    except (requests.ConnectionError, requests.exceptions.Timeout, AssertionError):
        return True
    else:
        return False

from bottle import request, response
from bottle import HTTPResponse
from settings import settings

def request_server_url():
  #print('ext_proto : %s' % settings['ext_proto'])
  #print('ext_ip : %s' % settings['ext_ip'])
  #print('ext_port : %s' % settings['ext_port'])

  try:
    if settings['ext_proto'] == 'https':
      proto = 'https://'
    else:
      proto = 'http://'
  except:
      proto = 'http://'

  try:
    port_int = int(settings['ext_port'])
    if port_int > 0:
      port = ':%s' % port_int
    elif port_int == 0:
      port = ''
    else:
      #invalid/negative value
      port = ':' + request.get('SERVER_PORT')
  except:
      # field not defined, or non-numerical
      port = ':' + request.get('SERVER_PORT')

  try:
    ip_num = socket.inet_aton(settings['ext_ip']) #just to make sure it's valid, and cause an exception otherwise
    ip = settings['ext_ip']
  except:
    ip, mac = get_node_ip()

  return proto + ip + port


def redirect(url, code=None):
  """ Aborts execution and causes a 303 or 302 redirect, depending on
  the HTTP protocol version. """
  print('Using private redirector')
  if not code:
    code = 303 if request.get('SERVER_PROTOCOL') == "HTTP/1.1" else 302
  res = response.copy(cls=HTTPResponse)
  res.status = code
  res.body = ""
  #res.set_header('Location', urljoin(request.url, url))
  #print('Request_url: %s' % request.url)
  #for a in request:
  #  print('%s : %s' % (a, request.environ.get(a)) )
  #Quick-n-Dirty: use relative URL. This conflicts with the HTTP/1.1 RFC!!
  #res.set_header('Location', url)

  full_url = request_server_url() + url
  print('Redirecting to: %s' % full_url)
  res.set_header('Location', full_url)
  raise res
