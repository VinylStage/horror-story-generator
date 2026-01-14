# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.5.0](https://github.com/VinylStage/horror-story-generator/compare/v1.4.0...v1.5.0) (2026-01-14)


### Features

* add in-process generation memory for similarity observation (Phase 2B) ([9f765b1](https://github.com/VinylStage/horror-story-generator/commit/9f765b18d4b4873fe37cab2810889e46ea572063))
* add model selection for story generation and Gemini prep for research ([cb53603](https://github.com/VinylStage/horror-story-generator/commit/cb53603539dc0d9258470429646cf0904c84eee5))
* add n8n API integration workflows and guide ([#39](https://github.com/VinylStage/horror-story-generator/issues/39)) ([4d33560](https://github.com/VinylStage/horror-story-generator/commit/4d33560981b62df870144c6b90df44b4ce34df9e)), closes [#9](https://github.com/VinylStage/horror-story-generator/issues/9)
* add sqlite story registry and high-only dedup control (Phase 2C) ([dec7144](https://github.com/VinylStage/horror-story-generator/commit/dec7144076bac564b5b7995ac0247850fb1660c1))
* **api:** add /research/dedup endpoint for semantic similarity ([cc8af5a](https://github.com/VinylStage/horror-story-generator/commit/cc8af5a711b0dfee16cd86f58dd25a9c0dd10af3))
* **api:** add background job monitoring and cancel support ([2733041](https://github.com/VinylStage/horror-story-generator/commit/273304178b472cef5d804e9cab8ded150c5b4c34))
* **api:** add batch job trigger API endpoints ([b2affdb](https://github.com/VinylStage/horror-story-generator/commit/b2affdb0a20a08db7869a1994451ceeb09e3c3c8))
* **api:** add batch job trigger API endpoints ([685f003](https://github.com/VinylStage/horror-story-generator/commit/685f00371e6a902272db13909c608ebd1296aabe))
* **api:** add dedup check endpoint for research jobs ([3c886b4](https://github.com/VinylStage/horror-story-generator/commit/3c886b48954968743de42d5ecc43f7605e54809b))
* **api:** add FastAPI server skeleton for research operations ([25bd2a9](https://github.com/VinylStage/horror-story-generator/commit/25bd2a95aaef301ce047a7bffe71889fbda09cfb))
* **api:** add file-based job manager for trigger API ([8d5f29c](https://github.com/VinylStage/horror-story-generator/commit/8d5f29c90017d30b59ff1b040a9f2e142b4cbd70))
* **api:** add Swagger documentation and poetry dependencies ([d5446b5](https://github.com/VinylStage/horror-story-generator/commit/d5446b57b2b5f816c2ad780e8f89f8f5c8cd404b))
* **api:** add trigger API endpoints for job execution ([aed5b62](https://github.com/VinylStage/horror-story-generator/commit/aed5b62f4a2363832da5978fbf0d8ef799b27848))
* **api:** add webhook notifications for job completion (v1.3.0) ([33151b5](https://github.com/VinylStage/horror-story-generator/commit/33151b570522000fcadf2b837262884b5a7a694d))
* **api:** connect API endpoints to CLI via subprocess ([8c04217](https://github.com/VinylStage/horror-story-generator/commit/8c042175e77983a8631676ce0822abb4cd096a6e))
* **infra:** add unified research context module ([d2e462e](https://github.com/VinylStage/horror-story-generator/commit/d2e462e824bde08fd95b4c515ec2a7cb8159edb1))
* **integration:** add research context injection and Phase B hooks ([af1f4bc](https://github.com/VinylStage/horror-story-generator/commit/af1f4bcf8329cf91be69de84c89cfad906cf8450))
* Phase 1 Foundation - Complete research, normalization, abstraction, and templates ([97b38f2](https://github.com/VinylStage/horror-story-generator/commit/97b38f28a008adad3a3e8906adf78861e8abc43c))
* Phase 2A - Template skeleton activation with random selection ([9dbd0c5](https://github.com/VinylStage/horror-story-generator/commit/9dbd0c5347dac4aa5e625426c82797894af4d64e))
* Phase 3B-B1 stabilization (daily logs + weighted template control) ([7c1270c](https://github.com/VinylStage/horror-story-generator/commit/7c1270ca43f06adb6f951f77fd61fc3f2175d4bd))
* **phase-b+:** add CLI commands for dedup and seeds ([4917fdb](https://github.com/VinylStage/horror-story-generator/commit/4917fdb6d7c86abb4a6df8e51f65c1e0aa48874a))
* **phase-b+:** add data_paths module for centralized path management ([8ff7e58](https://github.com/VinylStage/horror-story-generator/commit/8ff7e58f4c1c052981f798862c56b1926dc167d3))
* **phase-b+:** add Ollama resource management with auto-cleanup ([ccac653](https://github.com/VinylStage/horror-story-generator/commit/ccac653c07c8a52f8ffa662d360ed5c5514eaa1b))
* **phase-b+:** add research registry SQLite module ([4ffb555](https://github.com/VinylStage/horror-story-generator/commit/4ffb555baf31f0826d777c02ba16f53f78ff4d95))
* **phase-b+:** add research_dedup module with FAISS integration ([f4e93f6](https://github.com/VinylStage/horror-story-generator/commit/f4e93f6da4597a1e95ef28b512f9f790ece15f8d))
* **phase-b+:** add seed integration for story generation ([137e0c2](https://github.com/VinylStage/horror-story-generator/commit/137e0c29bb3239ab127b51a59717bc561ed9c0d9))
* **phase-b+:** add seed registry SQLite module ([5b2c606](https://github.com/VinylStage/horror-story-generator/commit/5b2c606228377e9947f943fe06432b8cd26b4b95))
* **phase-b+:** add story seed generation module ([7e3e6f5](https://github.com/VinylStage/horror-story-generator/commit/7e3e6f527fadcbe639b7e100eb7dd8ad4bf0ddd3))
* **research:** add canonical_core and dedup to research cards ([7204ee6](https://github.com/VinylStage/horror-story-generator/commit/7204ee6c84508d54cd9633a7591665e60360050b))
* **research:** add Gemini Deep Research Agent integration ([591a052](https://github.com/VinylStage/horror-story-generator/commit/591a052e89a26cc552934a8cdc9b001202062be4))
* **research:** add research_executor CLI package ([3695094](https://github.com/VinylStage/horror-story-generator/commit/3695094a212948d12d985af55bdd0bb54aa7ba8d))
* **story:** add research auto-injection with traceability ([d3b4c5b](https://github.com/VinylStage/horror-story-generator/commit/d3b4c5b9002cb196426138a774269c035b7afa7c))
* **story:** add story-level deduplication ([d88b99e](https://github.com/VinylStage/horror-story-generator/commit/d88b99e1038ad34c7368de112f123b674b764744))
* **story:** add topic-based story generation and API expansion ([fd42359](https://github.com/VinylStage/horror-story-generator/commit/fd423598b803779c815afba913fedbd9187765ce))


### Bug Fixes

* add issues write permission for release-please ([596b659](https://github.com/VinylStage/horror-story-generator/commit/596b6597b16282248545e6724fd79c9ebb7d7893))
* add issues write permission for release-please ([a9bc8ed](https://github.com/VinylStage/horror-story-generator/commit/a9bc8edc69a1484b17fc37598b66ed4067ffd97b))
* **api:** correct story router method name + add CLI + E2E test report ([6119d7b](https://github.com/VinylStage/horror-story-generator/commit/6119d7be5493446342da47be2c897c41b83edc29))
* **api:** propagate LLM errors as HTTP 502/504 instead of 200 OK ([c8eec66](https://github.com/VinylStage/horror-story-generator/commit/c8eec66626e4df4440ae5ca11a149b28562ec717))
* **api:** propagate LLM errors as HTTP 502/504 instead of 200 OK ([d9ac683](https://github.com/VinylStage/horror-story-generator/commit/d9ac6838cbc01ad35098a248b1b380e60e13e2d8))
* **api:** research CLI command format and zombie process detection ([ec68ae7](https://github.com/VinylStage/horror-story-generator/commit/ec68ae77bcb4de029d2795a2fbe0a66854533f1b))
* **dedup:** use nomic-embed-text for research embeddings ([ea2bc13](https://github.com/VinylStage/horror-story-generator/commit/ea2bc13b3ae084fb2a9e47e8801fe4ba4a6ad93b))
* **deps:** update FastAPI to 0.128.0 and starlette to 0.50.0 ([da56f82](https://github.com/VinylStage/horror-story-generator/commit/da56f826c6b99387eb29266d5b1d4026251f4bc7))
* prevent release-please workflow loop ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([3712361](https://github.com/VinylStage/horror-story-generator/commit/371236113182d1fc6b99d3e3bc1215197452d762))
* prevent release-please workflow loop ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([b4e75ed](https://github.com/VinylStage/horror-story-generator/commit/b4e75ed7b29baa585770372d3fa68d4c1b9da613))
* **registry:** add pre-migration backup hook ([5c97c8b](https://github.com/VinylStage/horror-story-generator/commit/5c97c8b9624d6a9c3b49f009427a0e8e7e6ab6a4))
* rename README ([ee6d18b](https://github.com/VinylStage/horror-story-generator/commit/ee6d18b5ab1a2eaf084c13cd66a16ee4569cf063))
* **research:** add Ollama model cleanup on CLI exit ([bc580ef](https://github.com/VinylStage/horror-story-generator/commit/bc580ef3b10de54e531d0f87c727f25f5d1eacab))
* **research:** load dotenv before imports, simplify GeminiDeepResearch ([b449132](https://github.com/VinylStage/horror-story-generator/commit/b449132343e7c163e4f1acac631a9acd4244aa30))
* reset all versions to 1.3.2 and clean invalid releases ([570c9f3](https://github.com/VinylStage/horror-story-generator/commit/570c9f3a488e364a9d1de7c50eb784f8888beb7c))
* reset all versions to 1.3.2 and clean invalid releases ([4a23c79](https://github.com/VinylStage/horror-story-generator/commit/4a23c796771b39010b1f94f6e13762ecb7470e31))
* **story:** add type safety to build_user_prompt for non-string inputs ([8adf1ff](https://github.com/VinylStage/horror-story-generator/commit/8adf1ff52a1b7a2b505a46eda71d635bffbab2a3))
* **story:** correct function names in src/story/__init__.py ([3f5f00b](https://github.com/VinylStage/horror-story-generator/commit/3f5f00bfa5642f5bec18147d5903f0b3bc7a5e17))
* **tests:** update mock paths for src/ package structure ([cf38847](https://github.com/VinylStage/horror-story-generator/commit/cf38847a3670f66566ce419ee5e6486b4c2618b4))
* **test:** update test_run_research_error to expect 502 ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([a941982](https://github.com/VinylStage/horror-story-generator/commit/a941982e8a4ca0671c17a7faaa0918dfc8d7c9cf))
* use token-based loop prevention for release-please ([24b90ea](https://github.com/VinylStage/horror-story-generator/commit/24b90ea31d84da6cf82ad4d2f317d54e231e9d10))
* use token-based loop prevention for release-please ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([45ffb6f](https://github.com/VinylStage/horror-story-generator/commit/45ffb6f0dad668b27d5f9e3c109614da02887a70))


### Code Refactoring

* cleanup and performance improvements ([47eb4c4](https://github.com/VinylStage/horror-story-generator/commit/47eb4c4e1f6423bd39c9791214b5841dff879a4d))
* **infra:** centralize path management and add job pruning (v1.3.1) ([ad14b6a](https://github.com/VinylStage/horror-story-generator/commit/ad14b6a23edfccd924dd4a6d39bdb17a1aa9e919))
* modularize horror_story_generator into separate modules ([2086805](https://github.com/VinylStage/horror-story-generator/commit/2086805b0ad0356e1f98e7851d7e92d45439d5c8))
* structural cleanup for Deep Research preparation ([073db6f](https://github.com/VinylStage/horror-story-generator/commit/073db6f4cc6b80fa8d69c9d8ff1df6dacb3994c3))
* **structure:** restructure docs and assets directories ([818095a](https://github.com/VinylStage/horror-story-generator/commit/818095a49d2c60bef9678c27b2d66b669976d2bd))
* **structure:** STEP 4-B-1 - Infra & Registry Isolation ([5fcf9e0](https://github.com/VinylStage/horror-story-generator/commit/5fcf9e0ac54473fa47bcedf01f93f891d902e671))
* **structure:** STEP 4-B-2 - Dedup Logic Reorganization ([5e54927](https://github.com/VinylStage/horror-story-generator/commit/5e54927011233e477f606f74714380568ffacc37))
* **structure:** STEP 4-B-3 - Story Pipeline Refactoring ([49b21bc](https://github.com/VinylStage/horror-story-generator/commit/49b21bcd5a46946aae420626fda4a9317db8603d))
* **structure:** STEP 4-B-4 - Research Pipeline Refactoring ([5ea1f4b](https://github.com/VinylStage/horror-story-generator/commit/5ea1f4b0976502d1005c3231343969f5801a261e))
* **structure:** STEP 4-B-5 - Entry Point Stabilization ([f2e97e6](https://github.com/VinylStage/horror-story-generator/commit/f2e97e6c2efb18fa56f7f524adb8f676a258e581))


### Documentation

* add actual generation test results to validation report ([491793e](https://github.com/VinylStage/horror-story-generator/commit/491793e87dcc37bd2922e884233fbb2388341ad2))
* add CLI resource cleanup and version sync documentation ([7b2f39f](https://github.com/VinylStage/horror-story-generator/commit/7b2f39f68d89f7211096f3bdb2be217ba65dcd72))
* add CLI resource cleanup verification report ([5111001](https://github.com/VinylStage/horror-story-generator/commit/51110012a4bc430a5ed31b5eeb7a665d22ab62c8))
* add dedup test results and research dedup setup guide ([c184533](https://github.com/VinylStage/horror-story-generator/commit/c184533191f4282edda4c556a3445afd4e9d5838))
* add full pipeline test verification report ([4e4726f](https://github.com/VinylStage/horror-story-generator/commit/4e4726fd148572b46ecb990454dabc6647b9f6c3))
* add Gemini Deep Research Agent documentation ([58e7969](https://github.com/VinylStage/horror-story-generator/commit/58e796956ad7df442eab56731a5e870f0ce717f1))
* add Gemini Deep Research verification report ([fb029d1](https://github.com/VinylStage/horror-story-generator/commit/fb029d188707bcbcb6aaba42bcbfcbd94bb5ef82))
* add KU to Canonical Key generation rules ([0014912](https://github.com/VinylStage/horror-story-generator/commit/001491262ccbcaf37c1c28cd51cbfcbb5e0f27ae))
* add model selection and Gemini API documentation ([e541ba9](https://github.com/VinylStage/horror-story-generator/commit/e541ba98167a8f2c10ddd11cddc7204a0825042a))
* add model selection verification report ([64cd7f9](https://github.com/VinylStage/horror-story-generator/commit/64cd7f9756a0a18fdd897f270bf9ca8e23f2ca77))
* add Phase 1 runbook, work log, and future vector backend notes ([1230a3b](https://github.com/VinylStage/horror-story-generator/commit/1230a3b2381bd7e2e13d7ad2b1c663ba87348c96))
* add Phase 1/2 implementation summaries and specs ([2e28e56](https://github.com/VinylStage/horror-story-generator/commit/2e28e568ef50fc1e2f57312117d485e92e422cc8))
* add release-please version annotations to all docs ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([7d2c563](https://github.com/VinylStage/horror-story-generator/commit/7d2c5635e400687390ea2edb1fcb4f9a8e0b4f1a))
* add STEP 4-B final change report ([c9b6c74](https://github.com/VinylStage/horror-story-generator/commit/c9b6c74172ff610413d554ff5294e00e60078615))
* add STEP 4-B validation report ([e92f093](https://github.com/VinylStage/horror-story-generator/commit/e92f093f21ecab269be4c9de6b3602e088e21ee3))
* add story-level dedup final verification report ([514692a](https://github.com/VinylStage/horror-story-generator/commit/514692a3951c90c1d8f742c3e2fbcbad59416733))
* add TRIGGER_API.md with Korean documentation ([8c531a0](https://github.com/VinylStage/horror-story-generator/commit/8c531a0dd90e1458ae71b994e972e3b26cd15fcc))
* add unified pipeline verification report ([e63309c](https://github.com/VinylStage/horror-story-generator/commit/e63309c515cb1b1d11b7b796c61311f15948c317))
* add v1.2.1 operational notes and verification status ([ae7e1fe](https://github.com/VinylStage/horror-story-generator/commit/ae7e1fe4f3acecffba18360e5987a9939cd49e17))
* add v1.2.1 release summary report ([61afb99](https://github.com/VinylStage/horror-story-generator/commit/61afb9970fac03c1e28e907b3c19f880283c397e))
* add v1.3.1 technical debt cleanup test report ([ac9420b](https://github.com/VinylStage/horror-story-generator/commit/ac9420ba0a38d2e2a86f7089451f59bd759de96f))
* add webhook notifications test report ([de06bf3](https://github.com/VinylStage/horror-story-generator/commit/de06bf350f584b23ce66fb6309c4ef28204b28e1))
* **api:** add missing endpoints and improve model selection docs ([756e90d](https://github.com/VinylStage/horror-story-generator/commit/756e90d354fee997f8ac076051c325050f402642))
* **api:** add OpenAPI 3.2.0 specification ([d9c4f78](https://github.com/VinylStage/horror-story-generator/commit/d9c4f78bf155ccd62f7fc9f297647b2f0a1ca084))
* **api:** fix OpenAPI version and add validation schemas ([c7e223a](https://github.com/VinylStage/horror-story-generator/commit/c7e223ab694476c0e853260ce56f035c2595f70c))
* archive historical analysis documents ([#24](https://github.com/VinylStage/horror-story-generator/issues/24)) ([67bf55c](https://github.com/VinylStage/horror-story-generator/commit/67bf55c34a4b7debe6c18cbfa769ee9aa631f38e))
* archive historical analysis documents ([#24](https://github.com/VinylStage/horror-story-generator/issues/24)) ([bb10476](https://github.com/VinylStage/horror-story-generator/commit/bb10476ac34ba555e73dfa47588d398d5f0706fe))
* consolidate scattered documentation ([62372a5](https://github.com/VinylStage/horror-story-generator/commit/62372a53761f184a009a0b1cd7b4372d4ae34dd2))
* consolidate scattered documentation ([316a84d](https://github.com/VinylStage/horror-story-generator/commit/316a84d3069ec5fe6cdec484f8d5ac8818290230))
* convert architecture diagrams to Mermaid ([dcc20a9](https://github.com/VinylStage/horror-story-generator/commit/dcc20a974efe5b29f849859c42527990852f828c))
* define canonical key application scope and add baseline tags ([61e974e](https://github.com/VinylStage/horror-story-generator/commit/61e974edb578744933c6b1b424f9b837991504f0))
* document environment variable restart requirement ([bc20b47](https://github.com/VinylStage/horror-story-generator/commit/bc20b47490cfe82a256723dab81a1807900ad619))
* document environment variable restart requirement ([189e61d](https://github.com/VinylStage/horror-story-generator/commit/189e61dbcfe602bad0fd97f1ac18a1b804f13856))
* eliminate all legacy references and align canonical baseline ([101df6a](https://github.com/VinylStage/horror-story-generator/commit/101df6a912b6f79cf258b299c3e55256a0432f45))
* full STEP 4-C documentation audit and alignment ([5d49252](https://github.com/VinylStage/horror-story-generator/commit/5d49252fb4e6244280bb4969feb1b67b21d0c358))
* move CONTRIBUTING.md to repository root for GitHub recognition ([d4474bb](https://github.com/VinylStage/horror-story-generator/commit/d4474bb8965dd71c673b5ad697f6e73de1b39209))
* Phase 2 preparation analysis (template limits & duplication risk) ([196b87d](https://github.com/VinylStage/horror-story-generator/commit/196b87dd99c7e19ab8713cadcbc5b88d9cf6700f))
* **phase-b+:** add comprehensive Phase B+ documentation ([80766a1](https://github.com/VinylStage/horror-story-generator/commit/80766a137ad4c9a78b752ceaa2476338c6897255))
* **phase-b:** add Phase B quality, dedup, and cultural scope documentation ([7d11a98](https://github.com/VinylStage/horror-story-generator/commit/7d11a98390f575d0b47cf38e05e4d66f826986c7))
* **readme:** update CLI reference with model options ([0cca187](https://github.com/VinylStage/horror-story-generator/commit/0cca187401f7f720c5cebaa9a91676b6a4815342))
* remove phase-based naming from directories and code ([6a2ae97](https://github.com/VinylStage/horror-story-generator/commit/6a2ae975488c662b0bb00b6dbb42f05943dbd198))
* remove phase-based naming from directories and code ([b31262d](https://github.com/VinylStage/horror-story-generator/commit/b31262d5087d3ffebb7a18a78f63bc5e3d85da02))
* rename GEMINI_MODEL env var to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([d979938](https://github.com/VinylStage/horror-story-generator/commit/d97993833414f1f54c8b2bb459c500534a527756))
* rename GEMINI_MODEL env var to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([aba554b](https://github.com/VinylStage/horror-story-generator/commit/aba554ba930445b7a6f8a4994bd598d5daa3840e))
* rename GEMINI_MODEL to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([fb3c048](https://github.com/VinylStage/horror-story-generator/commit/fb3c04827cd58c79252eaa018959d92bc911c9a7))
* rename GEMINI_MODEL to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([c6c4237](https://github.com/VinylStage/horror-story-generator/commit/c6c42374f9742e9fa2107abb010f1f003210e43d))
* STEP 4-C documentation alignment ([e878258](https://github.com/VinylStage/horror-story-generator/commit/e8782583e9f78b8e8e0bf52fef5ce0d035836246))
* **todo:** add TODO-029 for GEMINI_MODEL env var rename ([303a9a5](https://github.com/VinylStage/horror-story-generator/commit/303a9a51fe91be123e1f1b6258325ff8a78e7980))
* **todo:** add TODO-030 for Research API error propagation (P1) ([f4ed308](https://github.com/VinylStage/horror-story-generator/commit/f4ed3089694f9195d261f9dddfeab9c716ebab32))
* **todo:** add TODO-031 and detailed descriptions for API issues ([d218079](https://github.com/VinylStage/horror-story-generator/commit/d21807911c582179f53f3282641a372ed2bf33b7))
* **todo:** add TODO-032 for webhook support on sync endpoints ([190b528](https://github.com/VinylStage/horror-story-generator/commit/190b52872be17d1373c9e4ad2b615dd0ba05c762))
* update all document version headers to v1.3.2 ([f0ce1fd](https://github.com/VinylStage/horror-story-generator/commit/f0ce1fd8e28dcf890d24ce5ba2225f566569c86c))
* update API and architecture docs for v1.2.x story generation ([f39b54f](https://github.com/VinylStage/horror-story-generator/commit/f39b54f28eefd904c77acbb15134721edac9265e))
* update docs for n8n ([2a0838e](https://github.com/VinylStage/horror-story-generator/commit/2a0838ed9565838ea7bcc91d887d0943622ac6f5))
* update documentation for v1.3.0 webhook notifications ([59b40f6](https://github.com/VinylStage/horror-story-generator/commit/59b40f6ecbaf746e868dc893f7738cf8eead4ffd))
* update documentation for v1.3.1 technical debt cleanup ([77474ed](https://github.com/VinylStage/horror-story-generator/commit/77474edbae24e2053a6067597bbdf00b5709bd46))
* update legacy path references to data/novel (v1.3.1) ([3d26350](https://github.com/VinylStage/horror-story-generator/commit/3d26350db8fa5eb6f4b7c57a3a72a34b601dd44e))
* update README.md with new src/ package structure ([881efbe](https://github.com/VinylStage/horror-story-generator/commit/881efbece7bdda147e60c1255f8648ee868f7197))
* update version references to v1.3.2 ([a15c4b7](https://github.com/VinylStage/horror-story-generator/commit/a15c4b7f0a09cf906a2cfb99d9f71f18a0b1a7b2))
* v1.1.0 release documentation ([7a7b137](https://github.com/VinylStage/horror-story-generator/commit/7a7b137ba76d4526d650e789772634007d266f23))
* **versioning:** document version and release policy ([facd669](https://github.com/VinylStage/horror-story-generator/commit/facd6695888298f96c480311321104411b548981))


### Technical Improvements

* add CI workflow for PR validation ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([4ee1103](https://github.com/VinylStage/horror-story-generator/commit/4ee1103f9a0c71882eece61144f448d99ec1c64d))
* configure release-please for automatic versioning ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([684febd](https://github.com/VinylStage/horror-story-generator/commit/684febdd10765cca4506c205526a0b07aa290b71))
* migrate TODOs to GitHub Issues ([#1](https://github.com/VinylStage/horror-story-generator/issues/1)) ([f031078](https://github.com/VinylStage/horror-story-generator/commit/f031078d95cb11343b53f0eacdc522b33fbcedda))

## [1.4.0](https://github.com/VinylStage/horror-story-generator/compare/v1.3.2...v1.4.0) (2026-01-14)


### Features

* add n8n API integration workflows and guide ([#39](https://github.com/VinylStage/horror-story-generator/issues/39)) ([4d33560](https://github.com/VinylStage/horror-story-generator/commit/4d33560981b62df870144c6b90df44b4ce34df9e)), closes [#9](https://github.com/VinylStage/horror-story-generator/issues/9)
* **api:** add batch job trigger API endpoints ([b2affdb](https://github.com/VinylStage/horror-story-generator/commit/b2affdb0a20a08db7869a1994451ceeb09e3c3c8))
* **api:** add batch job trigger API endpoints ([685f003](https://github.com/VinylStage/horror-story-generator/commit/685f00371e6a902272db13909c608ebd1296aabe))


### Bug Fixes

* add issues write permission for release-please ([596b659](https://github.com/VinylStage/horror-story-generator/commit/596b6597b16282248545e6724fd79c9ebb7d7893))
* add issues write permission for release-please ([a9bc8ed](https://github.com/VinylStage/horror-story-generator/commit/a9bc8edc69a1484b17fc37598b66ed4067ffd97b))
* **api:** propagate LLM errors as HTTP 502/504 instead of 200 OK ([c8eec66](https://github.com/VinylStage/horror-story-generator/commit/c8eec66626e4df4440ae5ca11a149b28562ec717))
* **api:** propagate LLM errors as HTTP 502/504 instead of 200 OK ([d9ac683](https://github.com/VinylStage/horror-story-generator/commit/d9ac6838cbc01ad35098a248b1b380e60e13e2d8))
* prevent release-please workflow loop ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([3712361](https://github.com/VinylStage/horror-story-generator/commit/371236113182d1fc6b99d3e3bc1215197452d762))
* prevent release-please workflow loop ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([b4e75ed](https://github.com/VinylStage/horror-story-generator/commit/b4e75ed7b29baa585770372d3fa68d4c1b9da613))
* reset all versions to 1.3.2 and clean invalid releases ([570c9f3](https://github.com/VinylStage/horror-story-generator/commit/570c9f3a488e364a9d1de7c50eb784f8888beb7c))
* reset all versions to 1.3.2 and clean invalid releases ([4a23c79](https://github.com/VinylStage/horror-story-generator/commit/4a23c796771b39010b1f94f6e13762ecb7470e31))
* **test:** update test_run_research_error to expect 502 ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([a941982](https://github.com/VinylStage/horror-story-generator/commit/a941982e8a4ca0671c17a7faaa0918dfc8d7c9cf))
* use token-based loop prevention for release-please ([24b90ea](https://github.com/VinylStage/horror-story-generator/commit/24b90ea31d84da6cf82ad4d2f317d54e231e9d10))
* use token-based loop prevention for release-please ([#43](https://github.com/VinylStage/horror-story-generator/issues/43)) ([45ffb6f](https://github.com/VinylStage/horror-story-generator/commit/45ffb6f0dad668b27d5f9e3c109614da02887a70))


### Documentation

* add release-please version annotations to all docs ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([7d2c563](https://github.com/VinylStage/horror-story-generator/commit/7d2c5635e400687390ea2edb1fcb4f9a8e0b4f1a))
* **api:** add missing endpoints and improve model selection docs ([756e90d](https://github.com/VinylStage/horror-story-generator/commit/756e90d354fee997f8ac076051c325050f402642))
* archive historical analysis documents ([#24](https://github.com/VinylStage/horror-story-generator/issues/24)) ([67bf55c](https://github.com/VinylStage/horror-story-generator/commit/67bf55c34a4b7debe6c18cbfa769ee9aa631f38e))
* archive historical analysis documents ([#24](https://github.com/VinylStage/horror-story-generator/issues/24)) ([bb10476](https://github.com/VinylStage/horror-story-generator/commit/bb10476ac34ba555e73dfa47588d398d5f0706fe))
* consolidate scattered documentation ([62372a5](https://github.com/VinylStage/horror-story-generator/commit/62372a53761f184a009a0b1cd7b4372d4ae34dd2))
* consolidate scattered documentation ([316a84d](https://github.com/VinylStage/horror-story-generator/commit/316a84d3069ec5fe6cdec484f8d5ac8818290230))
* document environment variable restart requirement ([bc20b47](https://github.com/VinylStage/horror-story-generator/commit/bc20b47490cfe82a256723dab81a1807900ad619))
* document environment variable restart requirement ([189e61d](https://github.com/VinylStage/horror-story-generator/commit/189e61dbcfe602bad0fd97f1ac18a1b804f13856))
* **readme:** update CLI reference with model options ([0cca187](https://github.com/VinylStage/horror-story-generator/commit/0cca187401f7f720c5cebaa9a91676b6a4815342))
* remove phase-based naming from directories and code ([6a2ae97](https://github.com/VinylStage/horror-story-generator/commit/6a2ae975488c662b0bb00b6dbb42f05943dbd198))
* remove phase-based naming from directories and code ([b31262d](https://github.com/VinylStage/horror-story-generator/commit/b31262d5087d3ffebb7a18a78f63bc5e3d85da02))
* rename GEMINI_MODEL env var to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([d979938](https://github.com/VinylStage/horror-story-generator/commit/d97993833414f1f54c8b2bb459c500534a527756))
* rename GEMINI_MODEL env var to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([aba554b](https://github.com/VinylStage/horror-story-generator/commit/aba554ba930445b7a6f8a4994bd598d5daa3840e))
* rename GEMINI_MODEL to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([fb3c048](https://github.com/VinylStage/horror-story-generator/commit/fb3c04827cd58c79252eaa018959d92bc911c9a7))
* rename GEMINI_MODEL to GOOGLE_AI_MODEL ([#25](https://github.com/VinylStage/horror-story-generator/issues/25)) ([c6c4237](https://github.com/VinylStage/horror-story-generator/commit/c6c42374f9742e9fa2107abb010f1f003210e43d))
* **todo:** add TODO-029 for GEMINI_MODEL env var rename ([303a9a5](https://github.com/VinylStage/horror-story-generator/commit/303a9a51fe91be123e1f1b6258325ff8a78e7980))
* **todo:** add TODO-030 for Research API error propagation (P1) ([f4ed308](https://github.com/VinylStage/horror-story-generator/commit/f4ed3089694f9195d261f9dddfeab9c716ebab32))
* **todo:** add TODO-031 and detailed descriptions for API issues ([d218079](https://github.com/VinylStage/horror-story-generator/commit/d21807911c582179f53f3282641a372ed2bf33b7))
* **todo:** add TODO-032 for webhook support on sync endpoints ([190b528](https://github.com/VinylStage/horror-story-generator/commit/190b52872be17d1373c9e4ad2b615dd0ba05c762))
* update all document version headers to v1.3.2 ([f0ce1fd](https://github.com/VinylStage/horror-story-generator/commit/f0ce1fd8e28dcf890d24ce5ba2225f566569c86c))
* update version references to v1.3.2 ([a15c4b7](https://github.com/VinylStage/horror-story-generator/commit/a15c4b7f0a09cf906a2cfb99d9f71f18a0b1a7b2))


### Technical Improvements

* add CI workflow for PR validation ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([4ee1103](https://github.com/VinylStage/horror-story-generator/commit/4ee1103f9a0c71882eece61144f448d99ec1c64d))
* configure release-please for automatic versioning ([#34](https://github.com/VinylStage/horror-story-generator/issues/34)) ([684febd](https://github.com/VinylStage/horror-story-generator/commit/684febdd10765cca4506c205526a0b07aa290b71))
* migrate TODOs to GitHub Issues ([#1](https://github.com/VinylStage/horror-story-generator/issues/1)) ([f031078](https://github.com/VinylStage/horror-story-generator/commit/f031078d95cb11343b53f0eacdc522b33fbcedda))

## [1.3.2] - 2026-01-13

### Security

- **CVE-2025-27600** (High): Starlette DoS via Range header merging - Fixed
- **CVE-2024-47874** (Medium): Starlette DoS in multipart forms - Fixed

### Dependencies

- FastAPI: ^0.115.0 → ^0.128.0
- Starlette: 0.46.2 → 0.50.0

---

## [1.3.1] - 2026-01-13

### Changed

- **Path Centralization (TODO-017)**
  - All path management centralized in `src/infra/data_paths.py`
  - Consistent path resolution across all modules
  - Environment variable overrides for all major paths

- **Output Directory Unification (TODO-016)**
  - Default novel output: `data/novel` (previously `generated_stories/`)
  - New env var: `NOVEL_OUTPUT_DIR` for custom path
  - Backward compatible with existing `OUTPUT_DIR` env var

- **Job Pruning (TODO-019)**
  - Optional automatic job history cleanup
  - Age-based pruning: `JOB_PRUNE_DAYS` (default: 30)
  - Count-based pruning: `JOB_PRUNE_MAX_COUNT` (default: 1000)
  - Disabled by default: `JOB_PRUNE_ENABLED=false`

### Deprecated

- **Legacy research_cards.jsonl (TODO-018)**
  - Accessing legacy path now emits `DeprecationWarning`
  - Read-only support maintained for backward compatibility
  - Use `data/research/` directory structure instead

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NOVEL_OUTPUT_DIR` | `data/novel` | Story output directory |
| `JOB_DIR` | `jobs/` | Job files directory |
| `JOB_PRUNE_ENABLED` | `false` | Enable automatic job pruning |
| `JOB_PRUNE_DAYS` | `30` | Prune jobs older than N days |
| `JOB_PRUNE_MAX_COUNT` | `1000` | Keep at most N recent jobs |

### Files Modified

- `src/infra/data_paths.py` - Extended with novel, jobs, and legacy path functions
- `src/infra/job_manager.py` - Centralized paths, added pruning functions
- `src/infra/job_monitor.py` - Centralized paths
- `src/story/generator.py` - Centralized paths
- `main.py` - Deprecated `run_research_stub()`

---

## [1.3.0] - 2026-01-13

### Added

- **Webhook Notifications (TODO-020)**
  - HTTP POST callbacks on job completion
  - Configurable events: `succeeded`, `failed`, `skipped`
  - Retry logic with exponential backoff (3 attempts)
  - New fields: `webhook_url`, `webhook_events` in trigger requests
  - New response fields: `webhook_sent`, `webhook_error`

- **"Skipped" Job Status**
  - New status for expected skip scenarios (e.g., duplicate detection)
  - Semantically distinct from failure - represents expected behavior
  - Webhook-triggerable like succeeded/failed

### Changed

- `StoryTriggerRequest` and `ResearchTriggerRequest` schemas extended with webhook fields
- `JobStatusResponse` includes webhook delivery status
- `JobMonitorResult` includes `reason` and `webhook_processed` fields
- Job monitor now detects and reports duplicate detection as "skipped"

### Files Added

- `src/infra/webhook.py` - Webhook notification service

### Files Modified

- `src/infra/job_manager.py` - JobStatus extended, Job dataclass with webhook fields
- `src/infra/job_monitor.py` - Webhook integration, skip detection
- `src/api/schemas/jobs.py` - Request/response schemas with webhook support
- `src/api/routers/jobs.py` - Webhook configuration in triggers

---

## [1.2.1] - 2026-01-13

### Fixed

- API story router method name mismatch (`get_recent_stories` → `load_recent_accepted`)

### Added

- Story CLI module (`src/story/cli.py`) for topic-based generation testing

### Verified

- CLI topic-based story generation (with/without existing research)
- API story generation endpoints (`POST /story/generate`, `GET /story/list`)
- Auto research → story injection pipeline
- Story-level deduplication (signature-based)
- Model selection (Claude / Ollama)
- Full E2E pipeline integrity (11/11 tests PASS)

### Reference

- Bug fix commit: `6119d7b`
- Test report: `docs/verification/STORY_GENERATION_E2E_TEST.md`

---

## [1.2.0] - 2026-01-13

### Added

- **Model Selection**
  - Story generation: Claude Sonnet (default) or Ollama models
  - Research generation: Ollama (default) or Gemini models
  - CLI flag: `--model ollama:qwen3:30b` for story, `--model gemini` for research

- **Gemini Deep Research Agent**
  - Optional research execution mode using `deep-research-pro-preview-12-2025`
  - Google AI Studio integration (standard generate_content API)
  - CLI flag: `--model deep-research`
  - Environment: `GEMINI_ENABLED=true`, `GEMINI_API_KEY`

- **Full Pipeline Verification**
  - Comprehensive real-world execution tests (CLI + API)
  - Automated pipeline integrity checks
  - Verification reports in `docs/verification/`

### Changed

- Research executor now loads dotenv before module imports
- Simplified GeminiDeepResearchProvider to use standard API

### Verified

- CLI: Local research (Ollama), Story generation (Claude/Ollama)
- API: Health, research endpoints, story job triggers
- Pipeline: Research auto-injection, dedup modules, unit tests (21/21)

---

## [1.1.0] - 2026-01-12

**This release is operationally sealed.**

### Added

- **Unified Research→Story Pipeline**
  - Automatic research card selection based on template affinity
  - Research context injection into story prompts
  - Full traceability in story metadata (`research_used`, `research_injection_mode`)

- **Research-Level Deduplication**
  - FAISS-based semantic similarity using `nomic-embed-text`
  - Dedup levels: LOW (<0.70), MEDIUM (0.70-0.85), HIGH (≥0.85)
  - HIGH cards excluded from story injection by default

- **Story-Level Deduplication**
  - SHA256 signature based on `canonical_core + research_used`
  - Pre-generation duplicate check (before API call)
  - WARN mode (default): continues with alternate template
  - STRICT mode: aborts generation

- **Registry Backup Mechanism**
  - Automatic backup before schema migration
  - Backup naming: `{db}.backup.{version}.{timestamp}.db`
  - Non-destructive, stdlib-only implementation

- **CLI Resource Cleanup**
  - Research executor automatically unloads Ollama models after execution
  - Signal handlers (SIGINT/SIGTERM) for graceful shutdown
  - Prevents VRAM leakage during batch operations

- **Canonical Core Normalization**
  - 5-dimension fingerprinting (setting, fear, antagonist, mechanism, twist)
  - Consistent normalization across templates and research cards

### Changed

- Story registry schema upgraded to v1.1.0
  - Added `story_signature` column
  - Added `canonical_core_json` column
  - Added `research_used_json` column
  - Added signature index for fast lookups

- Unified version management
  - Single source of truth in `src/__init__.py`
  - All submodules import version from parent
  - Package version synced: pyproject.toml, API, health endpoint

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_INJECT_RESEARCH` | `true` | Enable research auto-injection |
| `RESEARCH_INJECT_TOP_K` | `1` | Number of cards to inject |
| `ENABLE_STORY_DEDUP` | `true` | Enable story-level dedup |
| `STORY_DEDUP_STRICT` | `false` | Abort on duplicate |

### Verified

- All verification axes passed
- Full pipeline smoke test passed
- No known blocking issues

---

## [1.0.0] - 2026-01-08

Initial release with basic story generation pipeline.

### Added

- Claude API-based horror story generation
- 15 template skeletons with canonical fingerprints
- 52 knowledge units across 4 categories
- SQLite-based story registry
- 24-hour continuous operation support
- Graceful shutdown handling
