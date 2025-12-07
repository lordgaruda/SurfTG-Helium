import re
from aiofiles import open as aiopen
from os import path as ospath

from bot import LOGGER
from bot.config import Telegram
from bot.helper.database import Database
from bot.helper.exceptions import InvalidHash
from bot.helper.file_size import get_readable_file_size
from bot.server.file_properties import get_file_ids
from bot.telegram import StreamBot

db = Database()

admin_block = """
                    <style>
                        .admin-only {
                            display: none;
                        }
                    </style>"""

hide_channel = """
                    <style>
                        .hide-channel {
                            display: none;
                        }
                    </style>"""


async def render_page(id, secure_hash, is_admin=False, html='', playlist='', database='', route='', redirect_url='', msg='', chat_id='', analytics=None):
    tpath = ospath.join('bot', 'server', 'template')
    if route == 'login':
        async with aiopen(ospath.join(tpath, 'login.html'), 'r') as f:
            html = (await f.read()).replace("<!-- Error -->", msg or '').replace("<!-- RedirectURL -->", redirect_url)
    elif route == 'admin':
        async with aiopen(ospath.join(tpath, 'admin.html'), 'r') as f:
            html_template = await f.read()
            # Simple template rendering for analytics data
            if analytics:
                html = html_template
                # Replace analytics placeholders
                for key, value in analytics.items():
                    if isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            html = html.replace(f"{{{{ analytics.{key}.{subkey} }}}}", str(subvalue))
                    elif isinstance(value, list):
                        # Handle lists (clients, recent_requests)
                        continue
                    else:
                        html = html.replace(f"{{{{ analytics.{key} }}}}", str(value))
                
                # Handle clients table
                clients_html = ""
                for client in analytics.get('clients', []):
                    workload_status = 'status-active' if client['workload'] > 0 else 'status-idle'
                    workload_text = 'Active' if client['workload'] > 0 else 'Idle'
                    clients_html += f"""
                    <tr>
                        <td>{client['id']}</td>
                        <td>@{client['username']}</td>
                        <td>{client['workload']}</td>
                        <td>{client['requests']}</td>
                        <td>{client['bandwidth']}</td>
                        <td><span class="status-badge {workload_status}">{workload_text}</span></td>
                    </tr>
                    """
                html = html.replace("{% for client in analytics.clients %}", "").replace("{% endfor %}", "")
                html = html.replace("""                    <tr>
                        <td>{{ client.id }}</td>
                        <td>@{{ client.username }}</td>
                        <td>{{ client.workload }}</td>
                        <td>{{ client.requests }}</td>
                        <td>{{ client.bandwidth }}</td>
                        <td>
                            {% if client.workload > 0 %}
                            <span class="status-badge status-active">Active</span>
                            {% else %}
                            <span class="status-badge status-idle">Idle</span>
                            {% endif %}
                        </td>
                    </tr>""", clients_html)
                
                # Handle recent requests
                recent_html = ""
                for req in analytics.get('recent_requests', []):
                    icon = '🎬' if req['type'] == 'stream' else '📥' if req['type'] == 'download' else '🔍'
                    recent_html += f"""
                <div class="activity-item">
                    <div class="activity-icon activity-{req['type']}">
                        {icon}
                    </div>
                    <div class="activity-details">
                        <div class="activity-type">{req['type'].capitalize()} Request</div>
                        <div class="activity-time">{req['timestamp']} - Client {req['client_id']}</div>
                    </div>
                </div>
                """
                html = html.replace("{% for request in analytics.recent_requests %}", "").replace("{% endfor %}", "")
                html = html.replace("""                <div class="activity-item">
                    <div class="activity-icon activity-{{ request.type }}">
                        {% if request.type == 'stream' %}🎬{% elif request.type == 'download' %}📥{% else %}🔍{% endif %}
                    </div>
                    <div class="activity-details">
                        <div class="activity-type">{{ request.type|capitalize }} Request</div>
                        <div class="activity-time">{{ request.timestamp }} - Client {{ request.client_id }}</div>
                    </div>
                </div>""", recent_html)
                
                # Handle chart data (convert to JSON)
                import json
                hourly = analytics.get('hourly', {})
                html = html.replace("{{ analytics.hourly.labels|tojson }}", json.dumps(hourly.get('labels', [])))
                html = html.replace("{{ analytics.hourly.requests|tojson }}", json.dumps(hourly.get('requests', [])))
                html = html.replace("{{ analytics.hourly.bandwidth|tojson }}", json.dumps(hourly.get('bandwidth', [])))
                
                # Handle conditional progress bars
                total_req = max(analytics.get('total_requests', 1), 1)
                stream_pct = int((analytics.get('stream_count', 0) / total_req) * 100)
                download_pct = int((analytics.get('download_count', 0) / total_req) * 100)
                search_pct = int((analytics.get('search_count', 0) / total_req) * 100)
                
                html = html.replace("{{ (analytics.stream_count / analytics.total_requests * 100)|int }}", str(stream_pct))
                html = html.replace("{{ (analytics.download_count / analytics.total_requests * 100)|int }}", str(download_pct))
                html = html.replace("{{ (analytics.search_count / analytics.total_requests * 100)|int }}", str(search_pct))
            else:
                html = html_template
    elif route == 'home':
        async with aiopen(ospath.join(tpath, 'home.html'), 'r') as f:
            html = (await f.read()).replace("<!-- Print -->", html).replace("<!-- Playlist -->", playlist)
            if not is_admin:
                html += admin_block
                if Telegram.HIDE_CHANNEL:
                    html += hide_channel
    elif route == 'playlist':
        async with aiopen(ospath.join(tpath, 'playlist.html'), 'r') as f:
            html = (await f.read()).replace("<!-- Playlist -->", playlist).replace("<!-- Database -->", database).replace("<!-- Title -->", msg).replace("<!-- Parent_id -->", id)
            if not is_admin:
                html += admin_block
    elif route == 'index':
        async with aiopen(ospath.join(tpath, 'index.html'), 'r') as f:
            html = (await f.read()).replace("<!-- Print -->", html).replace("<!-- Title -->", msg).replace("<!-- Chat_id -->", chat_id)
            if not is_admin:
                html += admin_block
    else:
        file_data = await get_file_ids(StreamBot, chat_id=int(chat_id), message_id=int(id))
        if file_data.unique_id[:6] != secure_hash:
            LOGGER.info('Link hash: %s - %s', secure_hash,
                        file_data.unique_id[:6])
            LOGGER.info('Invalid hash for message with - ID %s', id)
            raise InvalidHash
        filename, tag, size = file_data.file_name, file_data.mime_type.split(
            '/')[0].strip(), get_readable_file_size(file_data.file_size)
        if filename is None:
            filename = "Proper Filename is Missing"
        filename = re.sub(r'[,|_\',]', ' ', filename)
        if tag == 'video':
            async with aiopen(ospath.join(tpath, 'video.html')) as r:
                poster = f"/api/thumb/{chat_id}?id={id}"
                html = (await r.read()).replace('<!-- Filename -->', filename).replace('<!-- Poster -->', poster).replace('<!-- Size -->', size).replace('<!-- Username -->', StreamBot.me.username)
        else:
            async with aiopen(ospath.join(tpath, 'dl.html')) as r:
                html = (await r.read()).replace('<!-- Filename -->', filename).replace('<!-- Size -->', size)
    return html