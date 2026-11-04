# CHANGELOG

<!-- version list -->

## v0.4.1 (2026-11-04)

### Bug Fixes

- **release**: Dynamic version assertion in release metadata tests
  ([`2a0d2ca`](https://github.com/Diaszano/postgres-mcp/commit/2a0d2ca4a81b8a52b9e3cbb43ebbdc6f4be6103d))

### Build System

- **docker**: Upgrade to python 3.13 and configure dependabot conventions
  ([`e056825`](https://github.com/Diaszano/postgres-mcp/commit/e0568259b8b8aaf012d277615aa39cbb26c2b001))

### Code Style

- Format single-line imports in test_release_metadata.py
  ([`edbd184`](https://github.com/Diaszano/postgres-mcp/commit/edbd1841d20437c877ff3552462f4e3692bcdda8))


## v0.4.0 (2026-11-04)

### Bug Fixes

- Bound SQL cursor result fetching
  ([`4b03d8a`](https://github.com/Diaszano/postgres-mcp/commit/4b03d8a62fc5b21e8965f032d9aa5ebc55811cf2))

- Clean up bounded SQL operations on cancellation
  ([`e4ac3d7`](https://github.com/Diaszano/postgres-mcp/commit/e4ac3d7d1c0b9201de9c5b98e60d5864449c896f))

- Close remaining SQL security gaps
  ([`d7231c9`](https://github.com/Diaszano/postgres-mcp/commit/d7231c918813588739ac722365d7c793e0d4eaef))

- Close Task 2 error sanitization gaps
  ([`6d70ee1`](https://github.com/Diaszano/postgres-mcp/commit/6d70ee1d146e580fef775691e72922c0e7843db1))

- Enforce complete MCP query response budgets
  ([`3c00f67`](https://github.com/Diaszano/postgres-mcp/commit/3c00f67267bd875946c0ecf466b2fc7f81018a2c))

- Enforce restricted SQL policy defense in depth
  ([`ea3fbe7`](https://github.com/Diaszano/postgres-mcp/commit/ea3fbe747e94d103a2dcfa4bf52cc42fc2c9fd6c))

- Isolate HypoPG tuning across concurrent analyses
  ([`c6f18df`](https://github.com/Diaszano/postgres-mcp/commit/c6f18df7de8c9193a0cdaf666d4f5089e699477b))

- Pin hypothetical EXPLAIN to one PostgreSQL session
  ([`7929762`](https://github.com/Diaszano/postgres-mcp/commit/79297622651465f52d4fc4f6b176a02d0ff7f22a))

- Pin mcp[cli]<2.0 to prevent breaking import change #187
  ([#201](https://github.com/Diaszano/postgres-mcp/pull/201),
  [`15c8e33`](https://github.com/Diaszano/postgres-mcp/commit/15c8e33353546148acc2d8bd784551cf3905d1e2))

- Prefix unused result variable with underscore
  ([#132](https://github.com/Diaszano/postgres-mcp/pull/132),
  [`3ad5cff`](https://github.com/Diaszano/postgres-mcp/commit/3ad5cff193ce423cc47026964327f4fcf49172a3))

- Preserve database context in health and extension checks
  ([`c8e0cdc`](https://github.com/Diaszano/postgres-mcp/commit/c8e0cdc8ab74158d6cb2438906f65dffa76a0f95))

- Preserve pools across ordinary SQL errors
  ([`badb25e`](https://github.com/Diaszano/postgres-mcp/commit/badb25eb6ea6ac48e5e85be3a7e0dd7abd2d1574))

- Preserve unknown pagination status at row cap
  ([`f8e3d8f`](https://github.com/Diaszano/postgres-mcp/commit/f8e3d8f655df4b851b75414944fbf91eb2765c5b))

- Prevent database credentials in Docker logs
  ([`fa00b5c`](https://github.com/Diaszano/postgres-mcp/commit/fa00b5cd8d0c6500b8393b6d6814593b38e12900))

- Protect reserved query cursors from eviction
  ([`06d3775`](https://github.com/Diaszano/postgres-mcp/commit/06d37750bf7c3c7376b09ff01573a26dcb0ff080))

- Queued callers reuse a failed pool open
  ([`12a3553`](https://github.com/Diaszano/postgres-mcp/commit/12a3553b0ed5bedd2a92fd6207eeecd17cf51934))

- Rate limit forced catalog refresh
  ([`c23eba2`](https://github.com/Diaszano/postgres-mcp/commit/c23eba25800d0bd73f215a50b26c93bad039526b))

- Rate limit forced refresh from list_databases
  ([`7a2cf6f`](https://github.com/Diaszano/postgres-mcp/commit/7a2cf6fd7fdc54c2ce527bf3261ce78951116ed9))

- Reject databases revoked during acquisition
  ([`1fc78e2`](https://github.com/Diaszano/postgres-mcp/commit/1fc78e2a8a031311133d3247b82617a33298e8d4))

- Reject VACUUM in restricted mode
  ([`de7cd12`](https://github.com/Diaszano/postgres-mcp/commit/de7cd12f7872ffba318c4282b876e34bc9ddce21))

- Resolve pyright static type errors and stabilize test typing
  ([`0da81aa`](https://github.com/Diaszano/postgres-mcp/commit/0da81aa00424750fe3da74be31612a272dbd2e27))

- Retire idle pool when database is revoked
  ([`4ec6530`](https://github.com/Diaszano/postgres-mcp/commit/4ec65301d73f95bda75152e3b16a7dab6f06a215))

- Sanitize malformed database URI errors
  ([`2df08a2`](https://github.com/Diaszano/postgres-mcp/commit/2df08a28548e5f880c531410d5f7895b7449ab71))

- Sanitize public SQL and connection errors
  ([`4898b69`](https://github.com/Diaszano/postgres-mcp/commit/4898b69f9526b8678bed69f38bf1aa6b1c03a37a))

- Scope query statistics and tuning to current database
  ([`8c38f83`](https://github.com/Diaszano/postgres-mcp/commit/8c38f83b1c47cdd855a25e8d8708293700a99b64))

- Serialize pool open in DbConnPool
  ([`5fba242`](https://github.com/Diaszano/postgres-mcp/commit/5fba242684931b183a33a4e6a02750b7c23fb2ed))

- Shield shutdown closes and log closed databases
  ([`2735189`](https://github.com/Diaszano/postgres-mcp/commit/2735189438681dd505e8366b754c526dc5c21ad1))

- Show VACUUM rejection reason to users
  ([`a7ecb20`](https://github.com/Diaszano/postgres-mcp/commit/a7ecb20e4b921b1d1a941ee0464d2b7f4ac48b89))

- Standardize MCP error signaling
  ([`0342bc0`](https://github.com/Diaszano/postgres-mcp/commit/0342bc00a6b3a38082d4b08ad24d8848189f8498))

- Support PostgreSQL 12 in get_top_queries
  ([#132](https://github.com/Diaszano/postgres-mcp/pull/132),
  [`3ad5cff`](https://github.com/Diaszano/postgres-mcp/commit/3ad5cff193ce423cc47026964327f4fcf49172a3))

- Time out database discovery
  ([`b8253dd`](https://github.com/Diaszano/postgres-mcp/commit/b8253dd1fe785c875bbcf22a6b6cf082ee287e68))

- Unblock fork install and structure tool errors
  ([`aea8166`](https://github.com/Diaszano/postgres-mcp/commit/aea8166de9d7a813002bd93d7b468255ac4975c2))

- Validate restricted operator function resolution
  ([`f5ec853`](https://github.com/Diaszano/postgres-mcp/commit/f5ec853ecd222808dde0f80246177c6ed451d34e))

- **ci**: Download trivy binary directly from github release with sha256 check
  ([`ab0242b`](https://github.com/Diaszano/postgres-mcp/commit/ab0242b9d1928004a20856015f147b7a134d1623))

- **ci**: Make partial GHCR publication recoverable
  ([`4c4c544`](https://github.com/Diaszano/postgres-mcp/commit/4c4c544a285dae4f532a60849a868abdec89fabd))

- **query-limits**: Enforce strict tool input types
  ([`b681062`](https://github.com/Diaszano/postgres-mcp/commit/b681062beb046b9ffc7e575c2db6c3b0dbd1f33e))

- **release**: Make image promotion and recovery safe
  ([`488f912`](https://github.com/Diaszano/postgres-mcp/commit/488f912ccc06d7a96998fafe70b71fdabfe5396b))

- **release**: Propagate versioning and security failures
  ([`fdeb88f`](https://github.com/Diaszano/postgres-mcp/commit/fdeb88ff5e7b6a7ee7b8149894e908cb064b63b5))

- **release**: Validate existing tags before automated bootstrap
  ([`c484946`](https://github.com/Diaszano/postgres-mcp/commit/c484946da4dde6140e32bb34822144028f968140))

### Build System

- Automate dependency update pull requests
  ([`8450f02`](https://github.com/Diaszano/postgres-mcp/commit/8450f028c81f7126ad672d5c4bcbd02d017aedbf))

- Harden multi-architecture Docker release
  ([`d3a952c`](https://github.com/Diaszano/postgres-mcp/commit/d3a952c2128762edf41bbfb5711a2eac964e81dc))

- **deps**: Add testcontainers[postgres] to dev dependencies
  ([`eb0bcb3`](https://github.com/Diaszano/postgres-mcp/commit/eb0bcb3e7f4f5980b74b371ab0363ebab896964e))

- **release**: Configure semantic version policy
  ([`2a6b89f`](https://github.com/Diaszano/postgres-mcp/commit/2a6b89fe98d55d67137849905d43bd7c26ea7a3a))

- **release**: Synchronize locked dependencies and package assets
  ([`2ff6220`](https://github.com/Diaszano/postgres-mcp/commit/2ff622033a380537bb70143fb325dd5904c2a6ff))

### Chores

- Align developer commands and dependency lock
  ([`9bc17af`](https://github.com/Diaszano/postgres-mcp/commit/9bc17af06257b82f84eb48cc59ab40100e2e8822))

- Align local verification commands
  ([`a070b88`](https://github.com/Diaszano/postgres-mcp/commit/a070b88ad41119641a46469f7745397f1d39b6e4))

- Format test_multidb_server
  ([`04ebc89`](https://github.com/Diaszano/postgres-mcp/commit/04ebc898547ae4e5d1a6eb87eda135bd8755c27c))

- Lower default pool limits
  ([`1f97a41`](https://github.com/Diaszano/postgres-mcp/commit/1f97a4146013751ce64756849ab54aec3439f644))

- Update all dependencies to latest versions
  ([#130](https://github.com/Diaszano/postgres-mcp/pull/130),
  [`cc52408`](https://github.com/Diaszano/postgres-mcp/commit/cc5240805c0c6e5823ebaf3cbc2032d53234026b))

- **repo**: Standardize formatting and Docker build context
  ([`39deac9`](https://github.com/Diaszano/postgres-mcp/commit/39deac9bba6517323e0e2ceefaacd18032a6dcef))

### Code Style

- Format codebase with ruff and align pyright configuration
  ([`c032401`](https://github.com/Diaszano/postgres-mcp/commit/c032401f47b1fa6cf7ca26b2e3ac9fd4bd35cb64))

### Continuous Integration

- Add read-only PR validation workflow
  ([`b85d0b3`](https://github.com/Diaszano/postgres-mcp/commit/b85d0b32aab782c77b05697d9ccfc52cade71478))

- Enforce PostgreSQL HypoPG integration prerequisites
  ([`8685632`](https://github.com/Diaszano/postgres-mcp/commit/8685632f9ea49e2f0b12929af58fe5ffa205ccf9))

- Enforce pull request conventions consistently
  ([`a85af16`](https://github.com/Diaszano/postgres-mcp/commit/a85af16d4a82f502654786334bb75dbfb57946ad))

- Ensure hypopg image build supports postgres 17 and 18
  ([`8d683d3`](https://github.com/Diaszano/postgres-mcp/commit/8d683d39fb5eb847a82054676f1dad70ba5aa70e))

- Fix duplicate case-insensitive no_proxy env keys in ci workflow
  ([`9060c46`](https://github.com/Diaszano/postgres-mcp/commit/9060c4620e251d99dd3466509316d10573e53182))

- Fix invalid pinned action commit shas across workflows
  ([`f474155`](https://github.com/Diaszano/postgres-mcp/commit/f4741559ba91e8e6c264c13d0b04dc430d13676b))

- Gate Python quality and package metadata
  ([`19da443`](https://github.com/Diaszano/postgres-mcp/commit/19da44375f3adecb4f23164d9387d641f5b093f7))

- Gate reusable release after successful main checks
  ([`1b5f31c`](https://github.com/Diaszano/postgres-mcp/commit/1b5f31c10413b17422d816485a082fade2d89ae5))

- Require package and image release smoke tests
  ([`65c2c09`](https://github.com/Diaszano/postgres-mcp/commit/65c2c09e73f1216d6f984beff69156841bc50bb9))

- Require PostgreSQL and HypoPG integration checks
  ([`eeb768a`](https://github.com/Diaszano/postgres-mcp/commit/eeb768ab45c781d57740eeaf3bf691539165e3ba))

- Retire Docker Hub release workflow after GHCR verification
  ([`0049d86`](https://github.com/Diaszano/postgres-mcp/commit/0049d86957cdf06a21b9323f942cd55d57753fdb))

- Validate conventional pull request metadata
  ([`4a7ba20`](https://github.com/Diaszano/postgres-mcp/commit/4a7ba2006473a37930eaec4a33c047e95041a61f))

- **security**: Block vulnerable multiarch image promotion
  ([`b31b35b`](https://github.com/Diaszano/postgres-mcp/commit/b31b35b8361e3365bfd982edce68b63203591421))

- **security**: Pin actions and minimize token privileges
  ([`80e7949`](https://github.com/Diaszano/postgres-mcp/commit/80e7949afc80ef893891d242cadac0f7855fb123))

### Documentation

- Add CI/CD semantic release and GHCR design specifications and implementation plans
  ([`3e08c30`](https://github.com/Diaszano/postgres-mcp/commit/3e08c306ebbb6d94f31446e4b8e556aa632e185b))

- Add design doc for testcontainers migration and pg17/18 support
  ([`435b520`](https://github.com/Diaszano/postgres-mcp/commit/435b520953c760855cafacf8b0d3b979d8bd41bf))

- Add implementation plan for testcontainers migration and pg17/18
  ([`9252b2a`](https://github.com/Diaszano/postgres-mcp/commit/9252b2a990e766f6dbf56a70fc1d044315556df5))

- Add pt-BR translations of README files
  ([`31baf1e`](https://github.com/Diaszano/postgres-mcp/commit/31baf1e6215fe2100212d1c3cc0a1b8ed6aa75c0))

- Align fork documentation with automated GHCR releases
  ([`c17da64`](https://github.com/Diaszano/postgres-mcp/commit/c17da64a57fc6770c6331351b80b3140f264db9d))

- Align repository governance with verified delivery
  ([`91715f8`](https://github.com/Diaszano/postgres-mcp/commit/91715f822d7feb274b84a27470efab9c495a5cb8))

- Define project readiness scope and acceptance criteria
  ([`fc3990d`](https://github.com/Diaszano/postgres-mcp/commit/fc3990d1a253185680bf715c46e9405f6c3a32e1))

- Document contribution rules and upstream attribution
  ([`11d7707`](https://github.com/Diaszano/postgres-mcp/commit/11d7707f2d22a766154e1bfcb92a0737c1331e9d))

- Document multi-database setup and validate regression
  ([`775bd97`](https://github.com/Diaszano/postgres-mcp/commit/775bd971e4b4ac8e323eb475c9e161687803ccde))

- Document query budgets and cursor pagination
  ([`b9f1f0f`](https://github.com/Diaszano/postgres-mcp/commit/b9f1f0feca259a7f1cb8b4eca59f369401457f03))

- Document restricted-mode statements and refresh limits
  ([`0f0c4aa`](https://github.com/Diaszano/postgres-mcp/commit/0f0c4aa963a9dc476e2f2567a8365b6ca30df602))

- Document testcontainers adoption and pg 17/18 test matrix
  ([`c978c1e`](https://github.com/Diaszano/postgres-mcp/commit/c978c1e8feac72f0361214b4207158f52b55365c))

- Mark all implementation steps complete in plan
  ([`0366c1b`](https://github.com/Diaszano/postgres-mcp/commit/0366c1bc37b9cbe89cd7456d26cb1df618ee6c21))

- Mark all superpowers plans and roadmap items completed
  ([`2f2652c`](https://github.com/Diaszano/postgres-mcp/commit/2f2652ca708751984c7caefe8b51ee5175ad06d9))

- Mark plan 01 repository conventions completed
  ([`394a1ca`](https://github.com/Diaszano/postgres-mcp/commit/394a1cadce723af1b7e245916e6d39ddb8fd924e))

- Mark plan 02 ci quality gates completed
  ([`ef29f40`](https://github.com/Diaszano/postgres-mcp/commit/ef29f406ef5d0d26a4c50f80747aff2f56663930))

- Mark plan 03 semantic versioning completed
  ([`ca4f1cb`](https://github.com/Diaszano/postgres-mcp/commit/ca4f1cb1b15f6f3ea3d8dfd96b5fdcf1ec9d1f34))

- Plan incremental project readiness improvements
  ([`cdb8101`](https://github.com/Diaszano/postgres-mcp/commit/cdb81019c61a2cb1f1590e4b42af79b0ff8b95ee))

- Record GitHub governance and rollback procedure
  ([`3203158`](https://github.com/Diaszano/postgres-mcp/commit/3203158aff4eef2895b5f741c518bfe3b3a56265))

- Record multi-database correction plan and results
  ([`a31eec8`](https://github.com/Diaszano/postgres-mcp/commit/a31eec8cc78c09b8bd05de9ab716cab74f9382a4))

- Record project readiness baseline
  ([`6331da0`](https://github.com/Diaszano/postgres-mcp/commit/6331da09d797332bda9b0adba3133eadda2aceb4))

- Record readiness verification results
  ([`e3c9f1f`](https://github.com/Diaszano/postgres-mcp/commit/e3c9f1fea2257fe4ec872846365e2e6bea33f034))

- **plan**: Complete plan 04 supply chain security
  ([`78474a8`](https://github.com/Diaszano/postgres-mcp/commit/78474a8e69247a3ff57e79ba5ac79733be88463a))

- **plan**: Complete plan 05 ghcr delivery
  ([`721ee33`](https://github.com/Diaszano/postgres-mcp/commit/721ee33dc563c3bfa6005023519df9a08b6d4f10))

- **plan**: Complete plan 06 operations and cleanup
  ([`672a21d`](https://github.com/Diaszano/postgres-mcp/commit/672a21d811341568d80ec1065d2b3a66b5b3294f))

- **release**: Document automated release and recovery
  ([`b68b7d3`](https://github.com/Diaszano/postgres-mcp/commit/b68b7d31f940d330d7760ef6b6ec9ebe8e851ed2))

- **security**: Define vulnerability and artifact attestation policy
  ([`a4878a4`](https://github.com/Diaszano/postgres-mcp/commit/a4878a42959bc4fa0ac021dc85674b134de900eb))

### Features

- Add expiring principal-bound query cursors
  ([`dbb5810`](https://github.com/Diaszano/postgres-mcp/commit/dbb58105c44d4a70241fe09e96854283b53042db))

- Add opt-in low-cardinality metrics
  ([`d889183`](https://github.com/Diaszano/postgres-mcp/commit/d88918383d75f951f311f3c779e024d1b6041410))

- Add per-database lazy registry and leases
  ([`b0428d9`](https://github.com/Diaszano/postgres-mcp/commit/b0428d987c178d2ee008bdf688ee0aada8a5fc16))

- Add tool annotations for improved LLM tool understanding
  ([#122](https://github.com/Diaszano/postgres-mcp/pull/122),
  [`84916ef`](https://github.com/Diaszano/postgres-mcp/commit/84916ef2da8df0fb2637cccd5a4d72b1dc593e90))

- Add transaction-scoped PostgreSQL sessions
  ([`bbd7955`](https://github.com/Diaszano/postgres-mcp/commit/bbd7955d84bcc720dbf8ea02dc1143c0e0208278))

- Allow table-level ANALYZE in restricted mode
  ([`fd09f33`](https://github.com/Diaszano/postgres-mcp/commit/fd09f339c280179b90906448675c0b5b47749956))

- Bound registry pools and close them safely
  ([`fb1f559`](https://github.com/Diaszano/postgres-mcp/commit/fb1f5598a18fadc15c2750756549ee6b8adce457))

- Cache discovery with bounded stale fallback
  ([`6cc5396`](https://github.com/Diaszano/postgres-mcp/commit/6cc5396d7b039e23c713c42ce26f9dc67cbe8db2))

- Cap SQL row and response payload size
  ([`15afbd3`](https://github.com/Diaszano/postgres-mcp/commit/15afbd32038f9b234e4609741b1f76af9b511f95))

- Derive per-database connection info safely
  ([`1373a42`](https://github.com/Diaszano/postgres-mcp/commit/1373a421514d0b88ba97e313be80dcbfd77722d9))

- Discover authorized databases on bootstrap instance
  ([`eb70a73`](https://github.com/Diaszano/postgres-mcp/commit/eb70a738b0beff9699e88f344953dc7e24bacc63))

- Enforce cumulative limits across query pages
  ([`c73df3b`](https://github.com/Diaszano/postgres-mcp/commit/c73df3b5d58a7ca20891b70d55bc83c1e678c709))

- Enforce SQL execution deadlines and concurrency
  ([`d6bd835`](https://github.com/Diaszano/postgres-mcp/commit/d6bd835e4270f4e33b84dc178fd2cc7f091637ad))

- Expose cursor pagination through MCP tools
  ([`0fe4a53`](https://github.com/Diaszano/postgres-mcp/commit/0fe4a53361a2799f8ec234bf15c89cd9c3180ec1))

- Expose database discovery and safe startup defaults
  ([`d1a8ece`](https://github.com/Diaszano/postgres-mcp/commit/d1a8eceaafd9fdba0ad5711152927f43b70a158b))

- Generate deterministic offset and keyset pages
  ([`97e5cc3`](https://github.com/Diaszano/postgres-mcp/commit/97e5cc3c3ad6ba9dc710a8d682657d688fb72b27))

- Instrument database query and cursor lifecycle
  ([`a05f739`](https://github.com/Diaszano/postgres-mcp/commit/a05f7395ed22b4ea130a3f8d8be796fb2dd8a165))

- Integrate guarded query execution with MCP
  ([`08af54c`](https://github.com/Diaszano/postgres-mcp/commit/08af54c9efebb221cc3347da106fea8d572d2757))

- Parse multi-database configuration
  ([`ee2c89c`](https://github.com/Diaszano/postgres-mcp/commit/ee2c89c2dea173aa2c879e199bb72cf68d539611))

- Report degraded database status safely
  ([`57120c8`](https://github.com/Diaszano/postgres-mcp/commit/57120c8b788ec6ef36c83c7777cbfdd80fe81166))

- Require authenticated remote MCP deployment
  ([`689d2b4`](https://github.com/Diaszano/postgres-mcp/commit/689d2b407e012fe59d649118da5414cc6c43c802))

- Return structured MCP tool results and errors
  ([`66c04dd`](https://github.com/Diaszano/postgres-mcp/commit/66c04dd051f9d1072113a40236bf5cae746106f1))

- Route schema tools to selected database
  ([`83ce1b2`](https://github.com/Diaszano/postgres-mcp/commit/83ce1b281d73f806debf65911ca84fd7a325a2e7))

- Route SQL and explain with restricted guards
  ([`4f4a0fa`](https://github.com/Diaszano/postgres-mcp/commit/4f4a0faca403b3c5e9b94426364085e6b94dfa4d))

- Validate SQL budget configuration
  ([`a79b051`](https://github.com/Diaszano/postgres-mcp/commit/a79b05123ca621bef404994e59e90d944380a247))

- Validate SQL eligibility for pagination
  ([`77c6ebe`](https://github.com/Diaszano/postgres-mcp/commit/77c6ebe79cdb462815c521df6baff8d5821fb4d8))

- **ci**: Promote scanned release image to semver GHCR tags
  ([`e232e71`](https://github.com/Diaszano/postgres-mcp/commit/e232e71506386b44515d2cb138b2191bc3ada325))

- **ci**: Release verified main commits with semantic versioning
  ([`305fc67`](https://github.com/Diaszano/postgres-mcp/commit/305fc67eda1362eb3657f5746775da7410dd7ff3))

- **ci**: Stage attested multiarch images in GitHub registry
  ([`dd7c0fa`](https://github.com/Diaszano/postgres-mcp/commit/dd7c0fa398d8910f4da36214523344762160f86e))

- **query-limits**: Validate agent budget overrides
  ([`f81ce5e`](https://github.com/Diaszano/postgres-mcp/commit/f81ce5effa251e5cd7bb0d3f20701a4628a0ee5d))

### Performance Improvements

- Benchmark bounded SQL execution and pools
  ([`37af5be`](https://github.com/Diaszano/postgres-mcp/commit/37af5be20b09589c1bdb8f8dc8bc7b40e6b4ddb4))

### Refactoring

- Bind SQL driver to database lease per tool
  ([`410dbc5`](https://github.com/Diaszano/postgres-mcp/commit/410dbc55a3bf9940e5bce1adacb73acdc55295a8))

- Extract pg_stat_statements column logic to helper
  ([#133](https://github.com/Diaszano/postgres-mcp/pull/133),
  [`d03cf9f`](https://github.com/Diaszano/postgres-mcp/commit/d03cf9fcc86768d497809a1e12b72c5680f2ac86))

- Isolate MCP runtime in application lifespan
  ([`6ee6558`](https://github.com/Diaszano/postgres-mcp/commit/6ee655874417b5cd60bf5344e450f60f38c87ee7))

- Name bootstrap URI field per plan contract
  ([`6850450`](https://github.com/Diaszano/postgres-mcp/commit/685045060570a88ff3c499dd7326e9897274b7a9))

- Separate database inspection from MCP handlers
  ([`f4729d7`](https://github.com/Diaszano/postgres-mcp/commit/f4729d79852a2c4d4006951041ec3782d61274f1))

### Testing

- Assert connection errors propagate without manual flags
  ([`6a55da6`](https://github.com/Diaszano/postgres-mcp/commit/6a55da66931005c6da7d91bfb84455f7a4b17655))

- Assert extension probes are per database
  ([`4d9a949`](https://github.com/Diaszano/postgres-mcp/commit/4d9a9491866b27a6e3743900d348c91ab45d48ac))

- Characterize HypoPG session locality
  ([`8c7e09d`](https://github.com/Diaszano/postgres-mcp/commit/8c7e09d829637a30d9f26929874653e058756e84))

- Cover cursor pagination end to end
  ([`97f77ba`](https://github.com/Diaszano/postgres-mcp/commit/97f77ba2037e2e02d612dcf597e410f81b1a084c))

- Cover multi-database integration and isolation
  ([`031d949`](https://github.com/Diaszano/postgres-mcp/commit/031d949fcbd2077795468f46efd403c2ad7ee6d2))

- Drop vacuous pool flag asserts
  ([`d2c20cb`](https://github.com/Diaszano/postgres-mcp/commit/d2c20cbfd12cf96c8b7bc247ecc1baac53c1b198))

- Migrate create_postgres_container to testcontainers and add pg17/18
  ([`48553f8`](https://github.com/Diaszano/postgres-mcp/commit/48553f8dd27ab8476bfbcf59f6c124f73774ba16))

- Stabilize final readiness checks
  ([`b6ba76e`](https://github.com/Diaszano/postgres-mcp/commit/b6ba76eca4251a19f1dae27bafdd675787cd064f))

- Strengthen catalog and pool regression tests
  ([`b32451b`](https://github.com/Diaszano/postgres-mcp/commit/b32451b5c847866a0f9d0c3eb8929dd83c4b4d09))

- Tighten multi-database integration assertions
  ([`8edd02b`](https://github.com/Diaszano/postgres-mcp/commit/8edd02b240f5d9693f793b83cb670abea3589f99))

- Unify integration multidb container harness with testcontainers
  ([`ececfea`](https://github.com/Diaszano/postgres-mcp/commit/ececfea0b50a728069cdec512a78c80aaa324ba5))

- **ci**: Verify automated delivery contracts end to end
  ([`0010d8d`](https://github.com/Diaszano/postgres-mcp/commit/0010d8d7dd0d552a19c975b75f3752bfce2fb69b))

- **release**: Verify conventional commit version bumps
  ([`ccb1efe`](https://github.com/Diaszano/postgres-mcp/commit/ccb1efe58df5ceb6a0e445fc443b1047a99fda31))

- **security**: Cover pipeline trust boundaries
  ([`215622f`](https://github.com/Diaszano/postgres-mcp/commit/215622f9aa7e52712f399b7abc0d7320bd7716a8))


## v0.3.0 (2025-05-16)


## v0.2.0 (2025-04-16)


## v0.1.1 (2025-04-08)

- Initial Release
