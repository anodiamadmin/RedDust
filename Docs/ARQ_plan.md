**What ARQ is:**



ARQ is a Python library for running background jobs asynchronously. You give it a Python function, it runs it outside your main server process, in the background, without blocking anything.



**Why you need it here:**



When a user disconnects from a Syan session, your WebSocket disconnect handler fires. At that point you need to do three expensive things:



Run two PostgreSQL stored procedures that crunch dimension scores into a soul score snapshot

Send the full transcript to Gemini Flash for batch preference extraction

Write all results back to DB



These could take 5–15 seconds combined. But a WebSocket disconnect handler must return immediately — if it hangs, it blocks the server's event loop and degrades every other active session.



So instead of doing the work inline, you do this:



User disconnects

&#x20;   → disconnect handler fires

&#x20;   → enqueue job (takes \~1ms)

&#x20;   → disconnect handler returns immediately ✓

&#x20;   

&#x20;   ... 10 seconds later, in the background ...

&#x20;   

&#x20;   → ARQ worker picks up the job

&#x20;   → runs stored procs + Gemini call

&#x20;   → writes to DB

&#x20;   → done



The user's next session will have their updated soul score and preferences. They never feel the delay.



**Why Redis specifically:**



ARQ needs somewhere to store the job queue — a list of "jobs waiting to be picked up." It needs this store to be:



Fast — enqueuing must take \~1ms, not slow down the disconnect handler

Persistent enough — jobs shouldn't vanish if the worker restarts mid-job

Accessible by both processes — your FastAPI server (which enqueues) and your ARQ worker (which consumes) are separate processes; they need a shared store



Redis is an in-memory data store that satisfies all three. ARQ was specifically built on top of Redis — it uses Redis lists as its queue primitive.



The alternative would be using PostgreSQL as the queue (which works and eliminates Redis), but ARQ doesn't support that. You'd need a different library. For MVP, adding one docker run command is the path of least resistance.



**The full picture in one diagram:**



FastAPI server (your main process)

&#x20;   │

&#x20;   │  session ends

&#x20;   │

&#x20;   ├──► arq.enqueue("compute\_session\_soul\_score", user\_id, session\_id)

&#x20;   │         │

&#x20;   │         │  writes job to Redis list (\~1ms)

&#x20;   │         ▼

&#x20;   │       Redis

&#x20;   │         ▲

&#x20;   │         │  polls for jobs

&#x20;   │         │

ARQ Worker (separate process, you start with: python -m arq app.worker.WorkerSettings)

&#x20;   │

&#x20;   ├──► refresh\_session\_dimension\_scores()  \[PostgreSQL stored proc]

&#x20;   ├──► refresh\_soul\_score\_snapshot()       \[PostgreSQL stored proc]

&#x20;   └──► extract\_preferences\_from\_session()  \[Gemini Flash + DB writes]

