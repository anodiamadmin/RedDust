Objects \& Conversations:



A: Deterministic Data



1# RedDust User Identity object after Google login:

{

&#x20; "user\_identity":

&#x20; {

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



2# RedDust User Profile object after app onboarding:

{

&#x20; "user\_profile":

&#x20; {

&#x20;   "first\_name": "Sara",

&#x20;   "age": 22,

&#x20;   "music\_languages": \[{"lang\_id": "ESP", "rank": 1}, {"lang\_id": "ENG", "rank": 2}, {"lang\_id": "INS", "rank": 3}, {"lang\_id": "OTH", "rank": 4}],

&#x20;   "favorite\_artist": \[{"artst\_id": "000", "rank": 1}, {"artst\_id": "002", "rank": 2}, {"artst\_id": "999", "rank": 3}, {"artst\_id": "537", "rank": 4}],

&#x20;   "favorite\_genre": \[{"gnre\_id": "397", "rank": 1}, {"gnre\_id": "127", "rank": 2}, {"gnre\_id": "940", "rank": 3}],

&#x20;   "favorite\_decades": \[{"dkd\_id": "00", "rank": 1}, {"dkd\_id": "04", "rank": 2}, {"dkd\_id": "05", "rank": 3}],

&#x20;   "other\_preference\_info": "Percussion based authentic Arabian classical music. Folk songs from across the world. K-Pop."

&#x20; }

}

References:

music\_languages.lang\_id: ESP=Spanish, ENG=English, INS=Instrumental, OTH=Others, HND=Hindi, BNG=Bengali, URD=Urdu, KOR=Korean, MND=Mandarin, ... etc.

favorite\_artists.artst\_id: 000=Ariana Grande, 001=Kishore Kumar, 002=Black Pink, 003=Brian Adams, ... 999=Others

favorite\_genre.gnre\_id: 000=Pop, 001=Rock, 002=Reggae, 003=K-Pop, 004=Bollywood, 005=Ghazal, 006=Trans, 007=Jazz, 008=Rabindra Sangeet ... 999=Others

favorite\_decades.dkd\_id: 00=Recent, 01=2010s, 02=2000s, 03=90s, 04=80s, 05=70s, 06=60s and older





3# RedDust User's current Session Context object:

{

&#x20; "session\_context": {

&#x20;   "session\_id": "sess\_20260609\_160000\_abc123",

&#x20;   "login\_timestamp": "2026-06-09T16:00:00+10:00",

&#x20;   "timezone": "Australia/Sydney",

&#x20;   "time\_of\_day": "Afternoon",

&#x20;   "location": {"source": "device\_gps", "city": "Sydney", "state": "NSW", "country": "Australia", "latitude": -33.8688, "longitude": 151.2093, "permission\_granted": true},

&#x20;   "weather": {"source": "weather\_api", "condition": "Cloudy", "temperature\_c": 18, "feels\_like\_c": 16, "temperature\_band": "Cool", "is\_raining": false},

&#x20;   "calendar\_context": {"is\_weekend": false, "is\_public\_holiday": false, "holiday\_name": null}

&#x20; }

}



B: Probabilistic Info



\#4 RedDust User's Current SSC object:

Chat Step 1 — Warm opening + mood check-in: e.g.

&#x20; Syan: Hey Sara 💜 How are you feeling right now?

&#x20; Expected user answers: A bit tired./ Really excited./ Sad./ So-so./ Stressed./ Pretty good./ Overwhelmed.

{

&#x20; "user\_current\_ssc":

&#x20; {

&#x20;   "google\_user\_id": "13456789012345678901",				# ref "user\_identity"

&#x20;   "session\_id": "sess\_20260609\_160000\_abc123",			# ref "session\_context"

&#x20;   "safety\_flag": {"value": false, "unsafe\_converstaion": null, "safety\_flag\_reason": null, "safety\_flag\_time": "2026-06-09T16:00:00+10:00"},

&#x20;   "user\_mood": {"self\_decription": "A bit tired.", "captured\_at": "2026-06-09T16:00:00+10:00"},

&#x20;   "user\_current\_activity": {"self\_decription": "A bit tired.", "captured\_at": "2026-06-09T16:00:00+10:00"},

&#x20;   "life\_event": {"self\_decription": "Exam approaching!", "captured\_at": "2026-06-09T16:00:00+10:00", "impact\_severity": .75, "impact\_duration\_days": 30},

&#x20;   "user\_feel\_signals": {

&#x20;     "ssc1": {"name": "Spirit", "value": 0.45, "confidence": 0.65},

&#x20;     "ssc2": {"name": "Calmness", "value": null, "confidence": 0},

&#x20;     "ssc3": {"name": "Energy", "value": 0.30, "confidence": 0.85},

&#x20;     "ssc4": {"name": "Focus", "value": null, "confidence": 0}

&#x20;   },

&#x20;   "user\_life\_signals": {

&#x20;     "ssc5": {"name": "Motivation", "value": null, "confidence": 0},

&#x20;     "ssc6": {"name": "Connection", "value": null, "confidence": 0},

&#x20;     "ssc7": {"name": "Self\_Belief", "value": null, "confidence": 0},

&#x20;     "ssc8": {"name": "Purpose", "value": null, "confidence": 0}

&#x20;   }

&#x20; }

}

References:

All ssc# (Soul Score Component) values run from 0 to 1, Extremely-Low=0, Medium-Or-Neutral=0.5, Extremely-High=1

Confidence of each Soul Score Component runs from 0 to 1, Extremely-Low=0, Medium=0.5, Extremely-High=1



\#4 RedDust User's Current Activity object:

Chat Step 2 — Warm opening + mood check-in: e.g.

&#x20; Syan: I hear you 💜 What are you doing right now — studying, working, relaxing, travelling, or something else?



2\. Current Activity

3\. Major Life Events







Sara's Profiles:

DoB - 2004, location=Sydney, current time=4:00pm, Current date=Tuesday, 9-Jun-2026; \[language = English, Spanish, Korean], \[Genere = (pop, electro), decade=2020's], favorite artists = Sabrina Carpenter, Sriana Geande, Black Pink



Syan: Good afternoon Sara! How are you feeling now?



Sara: I am feeling a bit tired!/ I am really excited!/ I am sad!/ So so.

Syan tries to get: current psychological state and mood (Happy, Anxious, sad, delighted, positive etc.)



Syan: Hey Sara, thanks for sharing that. At 4 PM in Sydney, even the best playlists can't always beat a long day on their own.

Tell me, what's the story behind that tired feeling today? Are you relaxing at home, heading somewhere, studying, working, or out with friends?

Empathise as per current psychological state! Use Sara's profile \[DoB, location, current time, language] to frame this questions/ conversations. Ask why Sara is feeling this way? And what Sara's current life situation is like?



Sara: Yeah, I think it's mostly my exams. They're starting next week and I've still got so much revision left to do. I've been studying all day at home and I just feel a bit stretched and overwhelmed.

