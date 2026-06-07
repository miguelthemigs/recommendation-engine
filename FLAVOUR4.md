Personal Development Plan Flavour 4 - Deployment & DevOps
Recommendation Engine · Containers · CI/CD · Kubernetes · Semester 6 · 2026



Flavour 3 turned the recommendation engine into a scalable multi-user system: a real database, async job processing over a message bus, per-user authentication, rate limiting, and a load-tested architecture that scales near-linearly with workers. It works, and Cycle 5 proved it works under 100 concurrent users. But it has never left my laptop. The API runs from a terminal with `uvicorn --reload`, the worker runs in a second terminal, RabbitMQ runs in a single ad-hoc Docker container, the frontend's API URL is hardcoded to `localhost:8000`, and the CORS allowlist is hardcoded to `localhost`. There is no Dockerfile, no CI pipeline, no orchestration, and no public URL. "Scalable architecture" that only runs on one machine, started by hand, is only half the story.
This flavour closes that gap. It takes the exact same system and makes it deployable and deployed: every process containerized, a CI pipeline that tests and builds images on every push, the full backend orchestrated in Kubernetes with health probes and declarative manifests, and the whole stack reachable on a public URL — the frontend on Vercel, the Kubernetes backend exposed through a Cloudflare Tunnel — all on free tiers.


What are you going to do?
I will take the working Flavour 3 system and make it deployable and publicly accessible without changing what the application does:
Containerize every runtime process (FastAPI API, RabbitMQ worker, RabbitMQ broker) with Dockerfiles and a docker-compose file that brings the whole stack up with one command
Remove the two hardcoded deployment blockers: the frontend API URL becomes an injected environment variable, and the backend CORS allowlist becomes configurable
Build a CI pipeline on GitHub Actions that lints, runs the tests, builds the API and worker images, and pushes them to the GitHub Container Registry on every push to main
Orchestrate the backend in Kubernetes (minikube): deployments for the API, worker, and broker, a service and ingress, configuration and secrets, and liveness/readiness probes wired to the existing /health and /graph/stats endpoints
Deploy the frontend to Vercel and expose the Kubernetes backend through a Cloudflare Tunnel, so the full system is reachable on a public HTTPS URL
Optionally: add autoscaling so the worker pool grows and shrinks with the RabbitMQ queue depth, closing the loop on the manual worker-count scaling measured in Cycle 5

Learning Outcomes targeted: Engineering Approach, Software Quality, Software Maintenance, Professional Standard, Personal Leadership



Why is this relevant for you?
Everything I built in the first three flavours runs on my machine, started by hand. That is exactly the "works on my machine" state that the previous flavour was supposed to grow out of, and the architecture is genuinely good — it just isn't packaged, automated, or hosted anywhere. Deployment is the discipline that turns a working prototype into something a team can actually run, and it is the part of the lifecycle I have the least hands-on experience with.
Each piece of this flavour is a core industry skill. Containerization is how software is shipped today, so two processes that boot the same heavy in-memory graph need to become two reproducible images. A CI pipeline is the safety net every professional team relies on: tests and image builds happen automatically, not when someone remembers. Kubernetes is the de-facto standard for running multi-service systems, and this project is a perfect size to learn it honestly — three cooperating services, real health probes, real config and secret separation — without drowning in complexity. And getting it onto a public URL for free forces me to confront the real constraints of free-tier hosting, which is the situation most side projects and early-stage products actually live in. The frontend going on Vercel lets me deepen a tool I already know, while the Kubernetes backend pushes me into genuinely new territory.


Analyzing  (LO1 - Engineering Approach, LO4 - Professional Standard)
Before writing any deployment code I will research how to host a system like this one — a stateful in-memory engine plus a long-running worker plus a broker — on free infrastructure, because that constraint rules out a lot of the "just push to a PaaS" advice. The research compares where the frontend should live (Vercel vs alternatives) against where a stateful Kubernetes backend can run for free (local minikube exposed via a tunnel, versus always-on free-tier VMs like Oracle Cloud, versus container PaaS like Render or Fly.io), and weighs each on setup difficulty, what actually stays free, and how realistic the result is. It also covers the supporting decisions: Docker image strategy for two processes that share a heavy startup, which container registry to use, and what a CI pipeline can and cannot do against a backend that lives on a laptop. The output is a justified hosting decision before a single manifest is written.


Designing  (LO1 - Engineering Approach, LO3 - Software Maintenance)
The target architecture adds a deployment and orchestration layer on top of the unchanged Flavour 3 system:
Containers: the API and the worker each become an image built from the shared codebase; the broker is the official RabbitMQ image. A docker-compose file wires all three together for local development so the full stack runs with one command instead of three terminals.
CI/CD: GitHub Actions runs on every push — lint, tests, then build the API and worker images and push them to the GitHub Container Registry. The frontend is built and deployed separately by Vercel's own Git integration.
Kubernetes: the backend runs in minikube as three deployments (API, worker, broker) behind services, with an ingress as the single entry point. Configuration lives in a ConfigMap and secrets in a Kubernetes Secret, kept out of the images. The existing /health and /graph/stats endpoints become liveness and readiness probes, so the cluster only sends traffic once the in-memory graph is actually built.
Public edge: the frontend is hosted on Vercel; the Kubernetes ingress is exposed to the internet through a Cloudflare Tunnel, giving the frontend a stable public HTTPS URL to call. Supabase stays exactly as it is — already managed, already public.

The application code is left functionally untouched. The only source changes are turning two hardcoded values (the frontend API URL and the backend CORS allowlist) into injected configuration, which is itself a maintainability improvement the deployment forces into existence.


Realizing  (LO1, LO2, LO3)
Implementation follows the cycle plan. Each cycle has a concrete, testable deliverable that must work before the next cycle starts: a stack that comes up under docker-compose, a green CI pipeline with images in the registry, a healthy set of pods in minikube, and finally a working public URL. The optional autoscaling cycle depends on time remaining after the public deployment is verified.


Advising  (LO4 - Professional Standard)
I will document each deployment decision with its reasoning and its trade-offs, the same way the earlier flavours documented their architectural choices: why minikube plus a tunnel over an always-on free VM, what a multi-stage Docker build actually saves for a scikit-learn image, why secrets belong in a Kubernetes Secret rather than baked into an image, and what the real limits of "free" turned out to be in practice. Findings are recorded with evidence — pipeline runs, kubectl output, the live URL — not assumptions.


Managing & Control  (LO5 - Personal Leadership)
Cycles 1 to 5 are the committed scope. Cycle 6 (autoscaling) is explicitly optional and depends on time available after the public deployment in Cycle 5 is verified. Each cycle ends with a working, tested deliverable before I move on, so the work is never left in a half-deployed state. If a cycle surfaces a finding that changes the plan for the next one — a free tier that turns out not to be free, a tunnel limitation, an image that is too heavy — the deviation is documented with its reason, the same pattern I followed in the previous flavours.


How are you going to do it?
Research free-tier hosting for a stateful backend; decide frontend host, backend host, and registry with justified reasoning
Write Dockerfiles for the API and the worker; add a docker-compose file for API + worker + broker; verify the full stack comes up locally
Replace the hardcoded frontend API URL and backend CORS allowlist with injected environment configuration
Build the GitHub Actions pipeline: lint, test, build both images, push to the GitHub Container Registry
Write the Kubernetes manifests: deployments, services, ingress, ConfigMap, Secret, and liveness/readiness probes; bring the stack up in minikube
Deploy the frontend to Vercel with the API URL injected at build time
Expose the minikube ingress through a Cloudflare Tunnel and verify the full flow end to end on the public URL
If time: add queue-depth-based autoscaling for the worker pool and measure it against the manual scaling from Cycle 5


What expertise do you need?
Docker: writing Dockerfiles, multi-stage builds, image size and layer caching, .dockerignore, docker-compose for multi-service local setups
Container registries: pushing and pulling images, GitHub Container Registry, image tagging strategy
CI/CD: GitHub Actions workflows, jobs and steps, caching, building and pushing images, secrets in CI
Kubernetes: pods, deployments, services, ingress, ConfigMaps and Secrets, liveness and readiness probes, resource requests and limits, minikube
Twelve-factor configuration: environment-driven config, build-time vs runtime injection for a static frontend, keeping secrets out of images
Public exposure: Cloudflare Tunnel, DNS and HTTPS basics, CORS between a hosted frontend and a tunneled backend
Free-tier hosting landscape: Vercel, minikube, Oracle Cloud, Render, Fly.io — capabilities, limits, and what "free" actually means
Autoscaling (optional): horizontal pod autoscaling and queue-depth-driven scaling with KEDA


Cycle Planning

Cycle
Focus
Deliverable
LOs
1
Deployment Research
Justified free-tier hosting decision: frontend host, stateful Kubernetes backend host, and container registry, with trade-offs documented before any manifest is written.
LO1, LO4
2
Containerization
Dockerfiles for the API and worker, a docker-compose file bringing API + worker + broker up with one command, and the two hardcoded blockers (frontend API URL, backend CORS) turned into injected config.
LO1, LO2, LO3
3
CI/CD Pipeline
GitHub Actions pipeline that lints, tests, builds the API and worker images, and pushes them to the GitHub Container Registry on every push to main.
LO2, LO3, LO4
4
Kubernetes
Backend running in minikube: deployments for API, worker, and broker, a service and ingress, ConfigMap and Secret, and liveness/readiness probes wired to /health and /graph/stats. All pods healthy.
LO1, LO3
5
Public Deployment
Frontend on Vercel with the API URL injected, the minikube ingress exposed through a Cloudflare Tunnel, and the full flow (register → watchlist → cold-start) verified working on a public HTTPS URL.
LO1, LO3, LO4, LO5
6 (optional)
Autoscaling
Queue-depth-driven autoscaling for the worker pool (KEDA/HPA), closing the loop on the manual worker scaling measured in Cycle 5 of Flavour 3.
LO1, LO5
