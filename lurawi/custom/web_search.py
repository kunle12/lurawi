"""Custom behaviour for web search (Firecrawl/SearXNG) with simple and deep research modes, including iterative LLM-driven synthesis."""

import re
from urllib.parse import urlencode

import aiohttp

from lurawi.custom_behaviour import CustomBehaviour
from lurawi.utils import logger


class web_search(CustomBehaviour):
    """!@brief Performs web search or deep research using Firecrawl or SearXNG.

    Simple mode searches one or more queries and returns a list of results.
    Deep research breaks a question into sub-queries, iterates, optionally
    synthesizes via LLM, and returns a structured report with a summary.

    Backend auto-detection:
      - firecrawl_api_key provided  → Firecrawl
      - searxng_url provided        → SearXNG
      - neither                     → error + failed()

    Output is stored in the KB key specified by "content", defaulting to
    "WEB_SEARCH_RESULTS" (simple) or "DEEP_RESEARCH_RESULTS" (deep).

    Example (simple mode with Firecrawl):
    ["custom", { "name": "web_search",
                 "args": {
                            "search_terms": "latest AI news",
                            "max_results": 10,
                            "firecrawl_api_key": "fc-...",
                            "content": "WEB_SEARCH_RESULTS",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]

    Example (simple mode with SearXNG):
    ["custom", { "name": "web_search",
                 "args": {
                            "search_terms": "latest AI news",
                            "max_results": 10,
                            "searxng_url": "http://localhost:8888",
                            "content": "WEB_SEARCH_RESULTS",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]

    Example (deep research mode):
    ["custom", { "name": "web_search",
                 "args": {
                            "research_question": "Compare AI coding assistants in 2026",
                            "max_results": 20,
                            "max_iterations": 3,
                            "firecrawl_api_key": "fc-...",
                            "content": "DEEP_RESEARCH_RESULTS",
                            "llm_base_url": "http://localhost:1234/v1",
                            "llm_api_key": "not-needed",
                            "llm_model": "gpt-4o-mini",
                            "success_action": ["play_behaviour", "2"],
                            "failed_action": ["play_behaviour", "next"]
                          }
                }
    ]
    """

    FIRECRAWL_URL = "https://api.firecrawl.dev/v1/search"
    MAX_PAGE_CHARS = 10_000

    @staticmethod
    def _strip_html(text: str) -> str:
        """Strip common HTML tags for a plain-text approximation."""
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()

    async def _firecrawl_search(self, query: str, api_key: str, num_results: int = 5) -> list:
        """Search via Firecrawl API.

        POST /v1/search with the query, returning title/url/snippet/markdown
        for each result. Firecrawl handles both search ranking and page content
        extraction in a single call.

        Args:
            query: search string
            api_key: Firecrawl API key (fc-...)
            num_results: max results to return

        Returns:
            list of {"title", "url", "snippet", "content"} dicts
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "query": query,
            "limit": num_results,
            "scrape_options": {"formats": ["markdown"]},
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(self.FIRECRAWL_URL, json=payload) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error(
                            "web_search: Firecrawl returned %s: %s",
                            resp.status,
                            err_text,
                        )
                        return []

                    data = await resp.json()
                    results = []
                    web = data.get("web", [])
                    for item in web:
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "snippet": item.get("snippet", ""),
                                "content": item.get("markdown", ""),
                            }
                        )
                    return results

        except Exception as err:
            logger.error("web_search: Firecrawl error: %s", err)
            return []

    async def _searxng_search(self, query: str, base_url: str, num_results: int = 5) -> list:
        """Search via a SearXNG instance.

        GET /search?q=...&format=json against a SearXNG instance. Returns
        title/url/snippet only — full page content must be fetched separately
        via _fetch_page_content.

        Args:
            query: search string
            base_url: SearXNG instance URL (e.g. http://localhost:8888)
            num_results: max results to return

        Returns:
            list of {"title", "url", "snippet", "content": ""} dicts
        """
        params = {"q": query, "format": "json", "pageno": 1}
        url = f"{base_url.rstrip('/')}/search?{urlencode(params)}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error(
                            "web_search: SearXNG returned %s: %s",
                            resp.status,
                            err_text,
                        )
                        return []

                    data = await resp.json()
                    results = []
                    for item in data.get("results", []):
                        if len(results) >= num_results:
                            break
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "snippet": item.get("content", ""),
                                "content": "",  # filled later by _fetch_page_content
                            }
                        )
                    return results

        except Exception as err:
            logger.error("web_search: SearXNG error: %s", err)
            return []

    async def _fetch_page_content(self, url: str) -> str | None:
        """Fetch a URL and extract plain text.

        Used by SearXNG deep mode where full-page content is not included in
        search results. Strips HTML tags, caps at MAX_PAGE_CHARS.

        Args:
            url: page URL to fetch

        Returns:
            extracted plain text, or None on failure
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None
                    text = await resp.text()
                    text = self._strip_html(text)
                    if len(text) > self.MAX_PAGE_CHARS:
                        text = text[: self.MAX_PAGE_CHARS]
                    return text
        except Exception as err:
            logger.debug("web_search: fetch failed for %s: %s", url, err)
            return None

    async def _call_llm_for_synthesis(
        self, context: str, question: str, llm_base_url: str, llm_api_key: str, llm_model: str
    ) -> tuple[str, list[str]]:
        """Call LLM to synthesize research findings and identify knowledge gaps.

        Sends accumulated context to the LLM with a system prompt that asks
        for a coherent synthesis and then a list of follow-up questions.
        The LLM response is split on the separator "---GAPS---" to separate
        the synthesis from the gap questions.

        Args:
            context: accumulated page content from all searches so far
            question: the original research question
            llm_base_url: OpenAI-compatible base URL
            llm_api_key: API key
            llm_model: model name (e.g. gpt-4o-mini)

        Returns:
            (synthesis_text, [gap_question_strings]) — gaps capped at 3
        """
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=llm_api_key, base_url=llm_base_url)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research assistant. Synthesize the following web "
                    "search results into a coherent answer. Then list any "
                    "follow-up questions that would help fill remaining gaps. "
                    "Separate the synthesis from the questions with a line "
                    "containing exactly '---GAPS---'."
                ),
            },
            {
                "role": "user",
                "content": f"Research question: {question}\n\nSearch results so far:\n{context}",
            },
        ]

        try:
            resp = await client.chat.completions.create(
                model=llm_model,
                messages=messages,
                max_tokens=4096,
                temperature=0.4,
                stream=False,
            )
            content = resp.choices[0].message.content or ""
        except Exception as err:
            logger.error("web_search: LLM synthesis failed: %s", err)
            return "", []

        parts = content.split("---GAPS---")
        synthesis = parts[0].strip()
        gaps = []
        if len(parts) > 1:
            for line in parts[1].strip().split("\n"):
                line = line.strip().lstrip("1234567890.-* ")
                if line and len(line) > 10:
                    gaps.append(line)

        return synthesis, gaps[:3]  # cap at 3 follow-up queries

    async def _deep_research(
        self, question: str, max_results: int, max_iterations: int, backend: str, **kw
    ) -> dict:
        """Iterative deep research loop.

        For each iteration:
          1. Generate sub-queries from the question (or from LLM gap analysis)
          2. Search each sub-query via the chosen backend
          3. Fetch full page content (SearXNG) or use built-in markdown (Firecrawl)
          4. If LLM synthesis configured: call LLM to produce a summary and
             identify knowledge gaps; gaps become the next round's sub-queries
          5. Repeat until max_iterations or no more gaps
          6. Deduplicate results by URL

        Args:
            question: research question string
            max_results: max results per sub-query per iteration
            max_iterations: maximum search-reason rounds
            backend: "firecrawl" or "searxng"
            kw: may contain firecrawl_api_key, searxng_url, llm_base_url,
                llm_api_key, llm_model

        Returns:
            dict with keys:
              - results: deduplicated list of result dicts
              - summary: LLM synthesis (empty if LLM not configured)
              - queries_used: final list of sub-queries
              - total_sources: count of deduplicated results
        """
        # Generate initial sub-queries
        sub_queries = self._generate_sub_queries(question)
        accumulated = []
        all_results = []
        synthesis = ""

        for iteration in range(max_iterations):
            if not sub_queries:
                break

            # Search each sub-query
            for sq in sub_queries:
                if backend == "firecrawl":
                    results = await self._firecrawl_search(
                        sq, kw.get("firecrawl_api_key"), max_results
                    )
                else:
                    results = await self._searxng_search(sq, kw.get("searxng_url"), max_results)
                    # Fetch full content for each result
                    for r in results:
                        if r["url"]:
                            r["content"] = await self._fetch_page_content(r["url"])
                        else:
                            r["content"] = ""

                for r in results:
                    all_results.append(r)
                    if r.get("content"):
                        accumulated.append(r["content"])

            # Check if LLM synthesis is configured
            has_llm = all(kw.get(k) for k in ("llm_base_url", "llm_api_key", "llm_model"))

            if has_llm and accumulated:
                context = "\n\n---\n\n".join(accumulated[-20:])  # last 20 chunks
                synthesis, sub_queries = await self._call_llm_for_synthesis(
                    context,
                    question,
                    kw["llm_base_url"],
                    kw["llm_api_key"],
                    kw["llm_model"],
                )
            else:
                synthesis = ""
                sub_queries = []

        # Deduplicate results by URL
        seen = set()
        deduped = []
        for r in all_results:
            if r["url"] not in seen:
                seen.add(r["url"])
                deduped.append(r)

        return {
            "results": deduped,
            "summary": synthesis,
            "queries_used": sub_queries,
            "total_sources": len(deduped),
        }

    def _generate_sub_queries(self, question: str) -> list[str]:
        """Split a research question into 3 initial search queries.

        Uses a regex to split on connectors (and/or/,/vs/versus/compared to).
        Falls back to the full question plus two reformulations if fewer than
        3 parts are produced.

        Args:
            question: research question string

        Returns:
            list of 3 sub-query strings
        """
        # Simple heuristic: try splitting on connectors
        separators = re.split(
            r"\s+(and|or|,|vs\.?|versus|compared\s+to)\s+", question, flags=re.IGNORECASE
        )
        parts = [p.strip() for p in separators if len(p.strip()) > 15]

        if len(parts) >= 3:
            return parts[:3]

        # Fall back to the full question plus two reformulations
        return [
            question,
            f"{question} overview",
            f"{question} comparison",
        ]

    async def run(self):
        """Execute web search or deep research.

        Dispatch logic:
          1. If research_question is set → deep research mode
          2. If search_terms is set → simple search mode
          3. Backend chosen by which credentials are provided:
             firecrawl_api_key → Firecrawl, searxng_url → SearXNG
          4. If LLM endpoint args (llm_base_url + llm_api_key + llm_model)
             are provided, LLM synthesis runs automatically in deep mode
             and optionally fetches page content in simple mode

        Args (from self.details):
          - search_terms / research_question (str): the query
          - max_results (int, optional): defaults 5 simple / 10 deep
          - max_iterations (int, optional, deep only): defaults 3
          - firecrawl_api_key (str): Firecrawl API key
          - searxng_url (str): SearXNG instance base URL
          - content (str, optional): KB key for output
          - llm_base_url / llm_api_key / llm_model (optional): LLM synthesis
          - success_action / failed_action (list): workflow routing

        Output stored in KB:
          - Simple: {results: [...], total_sources: N}
          - Deep:   {results: [...], summary: str, queries_used: [...],
                     total_sources: N}
        """

        # --- Detect mode ---
        research_question = self.parse_simple_input(key="research_question", check_for_type="str")
        search_terms = self.parse_simple_input(key="search_terms", check_for_type="str")

        if research_question is None and search_terms is None:
            logger.error("web_search: missing search_terms or research_question")
            await self.failed()
            return

        is_deep = research_question is not None

        # --- Detect backend ---
        firecrawl_key = self.parse_simple_input(key="firecrawl_api_key", check_for_type="str")
        searxng_url = self.parse_simple_input(key="searxng_url", check_for_type="str")

        backend = None
        if firecrawl_key:
            backend = "firecrawl"
        elif searxng_url:
            backend = "searxng"
        else:
            logger.error(
                "web_search: missing credentials — provide firecrawl_api_key or searxng_url"
            )
            await self.failed()
            return

        # --- Parse shared params ---
        max_results = self.parse_simple_input(key="max_results", check_for_type="int")
        if max_results is None:
            max_results = 10 if is_deep else 5

        output_key = self.details.get("content") or (
            "DEEP_RESEARCH_RESULTS" if is_deep else "WEB_SEARCH_RESULTS"
        )

        # --- LLM synthesis config (optional) ---
        llm_base_url = self.parse_simple_input(key="llm_base_url", check_for_type="str")
        llm_api_key = self.parse_simple_input(key="llm_api_key", check_for_type="str")
        llm_model = self.parse_simple_input(key="llm_model", check_for_type="str")

        # --- Execute ---
        try:
            if is_deep:
                max_iterations = self.parse_simple_input(key="max_iterations", check_for_type="int")
                if max_iterations is None:
                    max_iterations = 3

                result = await self._deep_research(
                    research_question,
                    max_results=max_results,
                    max_iterations=max_iterations,
                    backend=backend,
                    firecrawl_api_key=firecrawl_key,
                    searxng_url=searxng_url,
                    llm_base_url=llm_base_url,
                    llm_api_key=llm_api_key,
                    llm_model=llm_model,
                )
            else:
                if isinstance(search_terms, str):
                    search_terms = [search_terms]

                all_results = []
                for st in search_terms:
                    if backend == "firecrawl":
                        results = await self._firecrawl_search(st, firecrawl_key, max_results)
                    else:
                        results = await self._searxng_search(st, searxng_url, max_results)
                        # Optionally fetch content in simple mode too
                        if llm_base_url and llm_api_key and llm_model:
                            for r in results:
                                if r["url"]:
                                    r["content"] = await self._fetch_page_content(r["url"])
                    all_results.extend(results)

                result = {"results": all_results, "total_sources": len(all_results)}

        except Exception as err:
            logger.error("web_search: execution error: %s", err)
            await self.failed()
            return

        # --- Store results ---
        if isinstance(output_key, str):
            self.kb[output_key] = result
        else:
            self.kb["WEB_SEARCH_RESULTS"] = result

        await self.succeeded()
