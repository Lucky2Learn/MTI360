"""Business domain modules (repository-structure.md §3).

Each module is a package with ``router → service → (domain, repository) →
models`` layering. A module calls another module only through its service, and
``app.core`` never imports a module (enforced by import-linter). The first
modules arrive in T01-02 onwards.
"""
