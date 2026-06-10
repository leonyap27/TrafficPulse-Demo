## Release manifest

* Version: {{ next_version }}
* Target environment: {{ target_env_detail }}
* Release date: TBD (set at sprint close)
* Approver (Tech Lead): {{ approver }}
* UAT Owner (optional): —
* PM (optional): —

> **Admin note:** create Jira project version `{{ next_version }}` (Project settings → Versions → Create), then set `Fix Version/s = {{ next_version }}` on this ticket so the version field is populated.

## Change summary

* TBD — fill in at sprint close.

## Bundle (included Jira items)

| Jira ID | Desc | Type | Status | Document (Y/N) |
| --- | --- | --- | --- | --- |
{% if carry_over -%}
{% for t in carry_over -%}
| [{{ t.key }}](https://ltads.atlassian.net/browse/{{ t.key }}) | {{ t.summary }} | carry-over | {{ t.status }} | {% if t.has_doc %}Y{% endif %} |
{% endfor %}
{% endif %}

## PR / commit references

* TBD

## Readiness checklist

- [ ] Code freeze on dev (commit SHA: TBD)
- [ ] Every linked Jira item in READY FOR DEPLOY
- [ ] UAT smoke test pass
- [ ] Approver (Tech Lead) sign-off — {{ approver }}

## Test evidence

* TBD

## Known issues / limitations

None reported.

---

_Auto-created by `/release-doc {{ prev_tracker_key }} YES` at sprint close. See `docs/3.0-deployment/RELEASE_TRACKER_SCHEMA.md` for the schema and `RELEASE_TRACKER_PLAYBOOK.md` for the operational flow._
