# План фикса проблем ревью PR #8

## Blocker 1: README описывает неправильный OAuth client type
- Заменить "TV and Limited Input" на "Web application"
- Добавить `http://127.0.0.1:8085` как Authorized redirect URI
- Убрать упоминание "user code" — сейчас это authorization code flow с localhost callback

## Blocker 2: Data API fallback теряет proxy
- `_fetch_via_captions_api` должен передавать `proxy=self._proxy_url`
- `fetch_transcript_via_data_api` должен принимать и прокидывать `proxy`

## Blocker 3: yt-dlp json3 download не использует proxy
- `fetch_transcript_via_ytdlp` должен скачивать json3 URL через proxy opener
- Использовать `get_proxy_url()` и `urllib.request.build_opener()`

## Major: OAuth token file не защищен правами доступа
- Добавить `os.chmod(token_file, 0o600)` после сохранения на POSIX
- На Windows — добавить комментарий в README о правах

## Major: Нет prompt=consent в OAuth URL
- Добавить `"prompt": "consent"` в `auth_params`
- Это гарантирует получение refresh_token

## Major: Ошибки fallback скрываются
- Собирать ошибки от каждого fallback в список
- Включать реальные причины в финальную ошибку

## Minor: _find_free_port по факту не ищет свободный порт
- Переименовать в `_ensure_port_free` или реально искать следующий свободный порт

## Тесты
- Проверить точный URL OAuth с параметрами
- Проверить proxy propagation в captions API
- Проверить proxy propagation в json3 download
- Проверить prompt=consent в URL
