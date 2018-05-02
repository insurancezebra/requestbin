import requests
import urllib
from flask import session, redirect, url_for, escape, request, render_template, make_response, Response, stream_with_context

from requestbin import app, db

def update_recent_bins(name):
    if 'recent' not in session:
        session['recent'] = []
    if name in session['recent']:
        session['recent'].remove(name)
    session['recent'].insert(0, name)
    if len(session['recent']) > 10:
        session['recent'] = session['recent'][:10]
    session.modified = True


def expand_recent_bins():
    if 'recent' not in session:
        session['recent'] = []
    recent = []
    for name in session['recent']:
        try:
            recent.append(db.lookup_bin(name))
        except KeyError:
            session['recent'].remove(name)
            session.modified = True
    return recent

@app.endpoint('views.home')
def home():
    return render_template('home.html', recent=expand_recent_bins())


@app.endpoint('views.inspect_bin')
def inspect_bin(name):
    try:
        bin = db.lookup_bin(name)
    except KeyError:
        return "Not found\n", 404

    if bin.private and session.get(bin.name) != bin.secret_key:
        return "Private bin\n", 403
    update_recent_bins(name)
    return render_template('bin.html',
        bin=bin,
        base_url=request.scheme+'://'+request.host)


@app.endpoint('views.bin')
def bin(name):
    parts = name.split('/', 1)
    bin_and_host = parts[0]
    path = parts[1] if len(parts) > 1 else ''

    bin_host_parts = bin_and_host.split('-')
    bin_name = bin_host_parts[-1]
    host = bin_host_parts[0] if len(bin_host_parts) > 1 else ''

    url = '%s://%s/%s?%s' % (request.scheme, host, path, request.query_string) if host else ''

    try:
        bin = db.lookup_bin(bin_name)
    except KeyError:
        return "Not found\n", 404

    db.create_request(bin, request)
    
    proxy_req = requests.request(
        method=request.method,
        url=url,
        headers={key: value for (key, value) in request.headers if (key != 'Host' and (key not in ('Content-Length', 'Content-Type') or value))},
        data=request.get_data(),
        cookies=request.cookies,
        stream=True)

    return Response(stream_with_context(proxy_req.iter_content()), content_type=proxy_req.headers.get('content-type'))


@app.endpoint('views.docs')
def docs(name):
    doc = db.lookup_doc(name)
    if doc:
        return render_template('doc.html',
                content=doc['content'],
                title=doc['title'],
                recent=expand_recent_bins())
    else:
        return "Not found", 404
