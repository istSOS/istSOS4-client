# Changelog

## 0.4.0

### Breaking changes

- `post()` returns the posted entity (with `iot_id` set) instead of the
  status code. `patch()` returns `None` instead of the status code.
- Options after the entity are keyword-only on every method:
  `commit_message`, `filter`, `expand`, `select`, `orderby`, `top`, `force`.

  ```python
  client.post(obs, "msg")                 # 0.3
  client.post(obs, commit_message="msg")  # 0.4
  ```

- `decode_result_quality(..., oasi=True)` is now its own function,
  `oasi_quality(...)`.
- `istsos4_client.utils` is now `istsos4_client.quality`. Top-level imports
  (`from istsos4_client import decode_result_quality`) are unchanged.

### Added

- `client.delete(Entity, id)`.
- `client.close()` and `with Client(url) as client:` to release connections.
- Type hints ship with the package (`py.typed`). `get()`, `list()`,
  `iter_list()` and `post()` return the entity class you pass in, e.g.
  `client.get(Thing, 1)` is typed as `Thing`.

### Changed

- Requests share one `requests.Session`, so connections are reused.
- Login uses the client's timeout and retries, and its errors carry the
  server's message like every other request.
