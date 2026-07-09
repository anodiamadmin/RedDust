1\. User Identity



Source: Google OAuth

Immutable



{

&#x20; "user\_identity": {

&#x20;   "google\_user\_id": "13456789012345678901",

&#x20;   "email": "sara.kim@gmail.com",

&#x20;   "email\_verified": true,

&#x20;   "full\_name": "Sara Kim",

&#x20;   "first\_name": "Sara",

&#x20;   "last\_name": "Kim",

&#x20;   "profile\_photo\_url": "https://lh3.googleusercontent.com/a/example",

&#x20;   "locale\_language": "en"

&#x20; }

}



2\. User Profile



Source: Onboarding

Rarely changes



{

&#x20; "user\_profile": {

&#x20;   "age": 22,



&#x20;   "music\_languages": \[

&#x20;     {"lang\_id": "ESP", "rank": 1},

&#x20;     {"lang\_id": "ENG", "rank": 2},

&#x20;     {"lang\_id": "INS", "rank": 3},

&#x20;     {"lang\_id": "OTH", "rank": 4}

&#x20;   ],



&#x20;   "favorite\_artists": \[

&#x20;     {"artist\_id": "000", "rank": 1},

&#x20;     {"artist\_id": "002", "rank": 2},

&#x20;     {"artist\_id": "999", "rank": 3},

&#x20;     {"artist\_id": "537", "rank": 4}

&#x20;   ],



&#x20;   "favorite\_genres": \[

&#x20;     {"genre\_id": "397", "rank": 1},

&#x20;     {"genre\_id": "127", "rank": 2},

&#x20;     {"genre\_id": "940", "rank": 3}

&#x20;   ],



&#x20;   "favorite\_decades": \[

&#x20;     {"decade\_id": "00", "rank": 1},

&#x20;     {"decade\_id": "04", "rank": 2},

&#x20;     {"decade\_id": "05", "rank": 3}

&#x20;   ],



&#x20;   "other\_music\_preferences": "Percussion based authentic Arabian classical music. Folk songs from across the world. K-Pop."

&#x20; }

}



3\. Current Session



Created at the beginning of every conversation

Deleted after the conversation



A. Device Context (objective)

{

&#x20; "device\_context": {

&#x20;   "timestamp\_utc": "2026-07-08T13:15:42Z",

&#x20;   "timezone": "Australia/Sydney",

&#x20;   "location": {

&#x20;     "city": "Sydney",

&#x20;     "country": "Australia"

&#x20;   },

&#x20;   "weather": {

&#x20;     "condition": "Cloudy",

&#x20;     "temperature\_c": 18

&#x20;   },

&#x20;   "calendar\_context": {

&#x20;     "is\_weekend": false,

&#x20;     "holiday\_name": null

&#x20;   }

}



B. Emotional Context (LLM-generated)

{

&#x20; "emotional\_context": {

&#x20;   "current\_mood": "Anxious",

&#x20;   "mood\_intensity": 8,

&#x20;   "primary\_life\_area": "Studies",

&#x20;   "desired\_outcome": "Calm"

&#x20; }

}



4\. Life Context



Continuously updated after conversations

This is NOT today's mood.

This is what is currently happening in the user's life.



{

&#x20; "life\_context": {

&#x20;   "active\_life\_areas": \[

&#x20;     {

&#x20;       "life\_area": "Studies",

&#x20;       "severity": 9

&#x20;     },

&#x20;     {

&#x20;       "life\_area": "Career",

&#x20;       "severity": 5

&#x20;     }

&#x20;   ],

&#x20;   "ongoing\_events": \[

&#x20;     "University semester examinations",

&#x20;     "Preparing internship applications"

&#x20;   ],

&#x20;   "current\_goal": "Reduce stress and stay focused.",

&#x20;   "updated\_on": "2026-07-08"

&#x20; }

}



5\. Conversation Summary



Instead of storing "AI memory", store a structured summary.



{

&#x20; "conversation\_summary": {

&#x20;   "summary": "Sara has been experiencing exam-related anxiety over the past week. She finds acoustic piano and soft instrumental music calming. She reported sleeping only five hours per night and wants to improve focus.",

&#x20;   "key\_takeaways": \[

&#x20;     "Exam stress",

&#x20;     "Sleep deprivation",

&#x20;     "Prefers calming instrumental music"

&#x20;   ],

&#x20;   "updated\_on": "2026-07-08"

&#x20; }

}



For every API call, send to LLM - your backend assembles:



{

&#x20; "system\_prompt": "...",

&#x20; "user\_identity": { ... },

&#x20; "user\_profile": { ... },

&#x20; "life\_context": { ... },

&#x20; "conversation\_summary": { ... },

&#x20; "current\_session": { ... },

&#x20; "recent\_messages": \[ ... ]

}







SAMPLE:



{

&#x20; "system\_prompt": "You are SyanBot, the AI companion of RedDust. Your role is to understand the user's emotions and life situation through conversation, then recommend music that can positively influence their wellbeing. Use all provided context naturally. Do not mention internal fields or JSON objects in your response.",



&#x20; "user\_identity": {

&#x20;   "google\_user\_id": "13456789012345678901",

&#x20;   "email": "sara.kim@gmail.com",

&#x20;   "email\_verified": true,

&#x20;   "full\_name": "Sara Kim",

&#x20;   "first\_name": "Sara",

&#x20;   "last\_name": "Kim",

&#x20;   "profile\_photo\_url": "https://lh3.googleusercontent.com/a/example",

&#x20;   "locale\_language": "en"

&#x20; },



&#x20; "user\_profile": {

&#x20;   "age": 22,

&#x20;   "music\_languages": \[

&#x20;     { "lang\_id": "ENG", "rank": 1 },

&#x20;     { "lang\_id": "KOR", "rank": 2 },

&#x20;     { "lang\_id": "ESP", "rank": 3 }

&#x20;   ],

&#x20;   "favorite\_artists": \[

&#x20;     { "artist\_id": "Coldplay", "rank": 1 },

&#x20;     { "artist\_id": "IU", "rank": 2 },

&#x20;     { "artist\_id": "Adele", "rank": 3 }

&#x20;   ],

&#x20;   "favorite\_genres": \[

&#x20;     { "genre\_id": "Pop", "rank": 1 },

&#x20;     { "genre\_id": "Acoustic", "rank": 2 },

&#x20;     { "genre\_id": "Indie", "rank": 3 }

&#x20;   ],

&#x20;   "favorite\_decades": \[

&#x20;     { "decade\_id": "2010s", "rank": 1 },

&#x20;     { "decade\_id": "2020s", "rank": 2 }

&#x20;   ],

&#x20;   "other\_music\_preferences": "Soft piano, acoustic guitar, rain ambience, emotional ballads."

&#x20; },



&#x20; "device\_context": {

&#x20;   "timestamp\_utc": "2026-07-08T13:15:42Z",

&#x20;   "timezone": "Australia/Sydney",

&#x20;   "location": {

&#x20;     "city": "Sydney",

&#x20;     "country": "Australia"

&#x20;   },

&#x20;   "weather": {

&#x20;     "condition": "Cloudy",

&#x20;     "temperature\_c": 18

&#x20;   },

&#x20;   "calendar\_context": {

&#x20;     "is\_weekend": false,

&#x20;     "holiday\_name": null

&#x20;   }

&#x20; },



&#x20; "emotional\_context": {

&#x20;   "current\_mood": "Anxious",

&#x20;   "mood\_intensity": 8,

&#x20;   "primary\_life\_area": "Studies",

&#x20;   "desired\_outcome": "Calm"

&#x20; },



&#x20; "life\_context": {

&#x20;   "active\_life\_areas": \[

&#x20;     {

&#x20;       "life\_area": "Studies",

&#x20;       "severity": 9

&#x20;     },

&#x20;     {

&#x20;       "life\_area": "Career",

&#x20;       "severity": 5

&#x20;     }

&#x20;   ],

&#x20;   "ongoing\_events": \[

&#x20;     "University semester examinations",

&#x20;     "Preparing internship applications"

&#x20;   ],

&#x20;   "current\_goal": "Reduce stress and stay focused.",

&#x20;   "updated\_on": "2026-07-08"

&#x20; },



&#x20; "conversation\_summary": {

&#x20;   "summary": "Sara has been experiencing exam-related anxiety over the past week. She finds acoustic piano and soft instrumental music calming. She reported sleeping only five hours per night and wants to improve focus.",

&#x20;   "key\_takeaways": \[

&#x20;     "Exam stress",

&#x20;     "Sleep deprivation",

&#x20;     "Acoustic piano helps relaxation"

&#x20;   ],

&#x20;   "updated\_on": "2026-07-08"

&#x20; },



&#x20; "recent\_messages": \[

&#x20;   {

&#x20;     "role": "assistant",

&#x20;     "content": "Hi Sara! It's good to see you again. How are you feeling today?"

&#x20;   },

&#x20;   {

&#x20;     "role": "user",

&#x20;     "content": "Honestly, I'm really nervous. My exams start next week and I can't focus."

&#x20;   }

&#x20; ]

}

