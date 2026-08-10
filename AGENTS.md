## Development

When starting the dev server, use background mode:

```
astro dev --background
```

Manage the background server with `astro dev stop`, `astro dev status`, and `astro dev logs`.

## Documentation

Full documentation: https://docs.astro.build

Consult these guides before working on related tasks:

- [Adding pages, dynamic routes, or middleware](https://docs.astro.build/en/guides/routing/)
- [Working with Astro components](https://docs.astro.build/en/basics/astro-components/)
- [Using React, Vue, Svelte, or other framework components](https://docs.astro.build/en/guides/framework-components/)
- [Adding or managing content](https://docs.astro.build/en/guides/content-collections/)
- [Adding styles or using Tailwind](https://docs.astro.build/en/guides/styling/)
- [Supporting multiple languages](https://docs.astro.build/en/guides/internationalization/)

## Check history before starting work

Before exploring files or writing code for any task that touches an existing module, file, or bug, call the history search tools first:

1. `find_related_work(query="<short description of the task>")` — has this exact task been worked on before?
2. If the task names a specific file, also call `find_sessions_by_file(file_path="...")`.
3. If step 1 returns nothing relevant, broaden with `search_history(query="...")` (full-text, no directory scope).

Only start exploring the codebase directly if history search comes up empty. If a relevant past session is found, read it with `get_session_detail` / `get_session_messages` before proceeding — don't repeat work or re-diagnose an issue that was already solved.
