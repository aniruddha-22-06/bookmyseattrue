# Scalable Genre/Language Filtering Notes

## Requirements Covered
- Multi-select server-side filtering by `genre` and `language`.
- Sorting + pagination with any filter combination.
- Dynamic facet counts:
  - Genre counts are computed after applying all non-genre filters.
  - Language counts are computed after applying all non-language filters.

## Data Model Strategy
- Added normalized lookup tables:
  - `Genre(name, slug)`
  - `Language(name, code)`
- Added `Movie.genres` and `Movie.languages` as many-to-many relations.
- This avoids denormalized comma-separated fields and keeps filters index-friendly.

## Query Optimization Choices
- Filtering is executed in SQL using join predicates (`genres__id__in`, `languages__id__in`) with `distinct()`.
- Pagination is database-driven via `LIMIT/OFFSET` from Django `Paginator`.
- Sorting is pushed to DB using indexed sortable fields (`name`, `rating`, `id`).
- Dynamic counts use SQL aggregation (`Count` + conditional filter), not Python loops over full catalogs.
- `prefetch_related('genres', 'languages')` avoids N+1 query behavior for list rendering.

## Indexing Strategy
- Added indexes:
  - `Movie(name)`, `Movie(rating)` for common sort/filter operations.
  - `Genre(name)`, `Genre(slug)`.
  - `Language(name)`, `Language(code)`.
- Django-generated M2M through-tables include FK indexes by default, helping join/filter performance at 5,000+ rows.

## Trade-offs
- `icontains` name search is flexible but can still scan at large scale in some DB engines.
  - For very large catalogs, consider trigram/full-text index (Postgres).
- `distinct()` is necessary to deduplicate rows after M2M joins but can add planner cost.
  - The cost is acceptable at current scale and keeps query semantics correct.
- Dynamic facet counts require extra aggregate queries.
  - This increases read query count but keeps UI counts correct without loading full datasets into memory.
