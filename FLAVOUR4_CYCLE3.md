# Flavour 4 — Cycle 3: Building a CI/CD Pipeline

*Recommendation Engine · Deployment & DevOps · Semester 6 · 2026*
*Learning Outcomes: LO1 (Engineering Approach), LO2 (Software Quality), LO3 (Software Maintenance), LO4 (Professional Standard)*

---

## 1. Where this cycle fits

In the previous cycle I packaged my whole backend into containers, so the
application could be started anywhere with a single command instead of three
terminals on my laptop. That solved *how* the software runs, but not *how it gets
checked and shipped*. Every time I changed the code, I was still the only safety
net: I had to remember to run things, test by hand, and build the image myself.
That is exactly the kind of manual, "hope I didn't forget anything" process that
breaks down the moment a project has more than one developer or more than a few
changes a week.

This cycle closes that gap by building a **CI/CD pipeline**: an automated process
that checks and packages my code on its own, every single time I push a change.

---

## 2. What a CI/CD pipeline actually is (in plain terms)

CI/CD stands for **Continuous Integration / Continuous Delivery**. Stripped of the
jargon, it is a robot assistant that watches my code repository. Whenever I send it
new code, the robot automatically runs a fixed checklist before that code is
considered "good". If any item on the checklist fails, it stops and tells me — so
broken code is caught immediately instead of weeks later.

Think of it like the quality gate at the end of a factory line. A product doesn't
leave the building until it has passed inspection, and the inspection is the same
every time, run by a machine rather than a tired human. My "products" are two
things: code that other people can trust, and a ready-to-run package of my
application.

I used **GitHub Actions** as the robot, because my code already lives on GitHub and
Actions is built directly into it — no extra service to sign up for or pay for.

---

## 3. The decisions I made *before* writing anything

A habit I have kept through every flavour is to decide the shape of the work before
diving into it, and to write down *why*. For this cycle I had three real choices to
settle first:

1. **How do I "test" code that had no tests yet?**
   My project only had performance/load tests, which need a live system and can't
   run inside an automated checklist. I had two options: write a tiny throwaway
   check that just boots the app, or invest in a small set of proper unit tests.
   I chose to **write real unit tests**, because they give lasting value — they
   document how my core logic is supposed to behave and they keep protecting me in
   every future cycle, not just this one.

2. **Which tool inspects code quality?**
   I picked **Ruff**, a modern, very fast code-quality checker for Python. The
   alternative was an older, slower tool with no real advantage. Choosing the
   current industry-standard tool is itself part of working professionally.

3. **Should the pipeline also cover the frontend?**
   No. My frontend is already automatically built and deployed by its own hosting
   platform (Vercel). Duplicating that work would add maintenance for no benefit, so
   I deliberately scoped this pipeline to the **backend only**. Knowing what to
   *leave out* is as much a design decision as what to put in.

Making these calls up front — and recording the trade-offs — meant the
implementation afterwards was fast and uncontroversial.

---

## 4. The steps of the pipeline

My pipeline runs as a sequence of stages. The first two run on *every* change
(including proposed changes from others). The final stage only runs once a change
is actually accepted into the main version of the project.

**Stage 1 — Lint (check code quality).**
The robot scans the code for sloppy or risky patterns: things imported but never
used, variables that go nowhere, obvious mistakes. This keeps the codebase tidy and
catches small errors before they grow. While setting this up, the tool found eight
such issues in my existing code, which I cleaned up.

**Stage 2 — Test (check the logic works).**
The robot installs the project and runs my new automated tests, which check that the
heart of the recommendation engine behaves correctly — that similarity scores are
calculated right, that the recommendation graph links the right items, and so on.
If any test fails, the pipeline stops here. I deliberately designed these tests to
be **self-contained**: they don't reach out to the database or any external service,
so they run fast and never fail for reasons outside my code.

**Stage 3 — Build and publish (package the application).**
Only if the first two stages pass *and* the change is going into the main version,
the robot builds my application into a container image and uploads it to an online
**registry** (a storage place for ready-to-run application packages). Each package
is labelled twice: once as "latest", and once with a unique fingerprint of the exact
code version it was built from. That fingerprint matters for the next cycle, where I
deploy to a server cluster and need to point at one *exact*, known version.

A small but important detail: the publishing stage is locked down so it only runs
for trusted changes, and it uses a short-lived, automatically-managed credential
rather than any password I store myself. Handling secrets safely was a specific
thing I wanted to get right.

---

## 5. How I worked

The process mirrored how I have approached the earlier flavours:

- **Interview, then execute.** I first clarified the open questions (the three
  decisions above), then implemented in one focused pass once the direction was
  clear.
- **Verify locally before trusting the robot.** I installed and ran the same checks
  on my own machine first — the quality scan came back clean and all of the tests
  passed — so I wasn't using the pipeline itself as my first test of whether the
  pipeline was correct.
- **Keep the change honest.** A rule I set for this whole flavour is that I am only
  changing *how* the software is packaged and shipped, never *what it does*. The only
  edits to the actual application were the eight small quality cleanups, none of which
  change its behaviour. I noted this explicitly so the boundary stays clear.
- **Don't claim "done" prematurely.** A pipeline can only be proven by actually
  running it on the real platform. Until that first run comes back green and the
  package appears in the registry, I am keeping this cycle marked as *built but not
  yet verified*, rather than ticking it off early.

---

## 6. What I learned

- **Automation is really about trust, not speed.** The point of the pipeline isn't
  that the robot is faster than me (though it is). It's that the same checks happen
  *every single time*, with no chance of me forgetting a step under pressure. That
  consistency is what lets a team move quickly without breaking things.
- **A pipeline forces you to make your project checkable.** I couldn't automate
  testing until I had tests, and I couldn't have fast tests until I separated my core
  logic from the database and external services. The act of building the pipeline
  pushed my project to be more cleanly structured — a maintainability win I got
  almost for free.
- **Good engineering is also about scope.** Choosing *not* to put the frontend in
  this pipeline, and choosing to keep the test tooling out of the shipped
  application, were both about keeping each piece doing one job well.
- **Security is in the small defaults.** Restricting *when* the publish step runs and
  *what* credentials it uses are tiny configuration choices, but they are the
  difference between a safe pipeline and a leaky one.

---

## 7. Honest limitations and what's next

- The pipeline **cannot deploy** my backend by itself. The next cycle runs the
  application on a local server cluster on my own machine, and an automated robot in
  the cloud has no access to that machine. So the pipeline's job ends at *publishing
  the package*; installing it onto the cluster stays a manual step for now. I'd
  rather state that limit clearly than pretend the automation goes further than it
  does.
- The first run on the real platform may need a one-time permissions setup before the
  published package is visible and usable. That is expected for a first-time setup.

With a trusted, automatically-built package now available, the next cycle can pull
that exact package and run the full backend on a Kubernetes cluster — which is where
the "fingerprinted version" labelling pays off.

---

## 8. How this maps to the Learning Outcomes

- **LO1 — Engineering Approach.** I researched and chose the right tools for the job
  (Ruff for quality, GitHub Actions for automation), and designed the pipeline
  deliberately — the order of the stages, what runs on every change versus only on the
  main version, and how the package is labelled — making each technical decision with a
  justified reason before building.
- **LO2 — Software Quality.** I introduced automated quality checks and a real test
  suite where there were none, and wired them into a gate that every change must pass.
- **LO3 — Software Maintenance.** Building the pipeline pushed the project toward a
  cleaner, more testable structure, and produced reproducible, version-labelled
  packages that make future deployment and rollback straightforward.
- **LO4 — Professional Standard.** I made deliberate tool and scope decisions with
  documented reasoning, handled credentials safely, and reported the result honestly
  — including what the pipeline deliberately does *not* do.
