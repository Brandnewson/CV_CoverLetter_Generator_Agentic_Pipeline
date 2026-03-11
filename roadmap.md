The following is the plan for what requirements I desire from now and into the future. They don't all have to be implemented at once, but develop with them in mind. 

Overarching roadmap:

The current development cycle will be to ensure the following pipeline can be met. 
1. The user will be able to automatically see everything about a company's job description, including keywords, nice-to-haves, key technical skills and requirements for the job. 
2. The backend will make use of all this information, and correctly rephrase/generate bullet points to be included in the CV, which will only occupy 1 line of the CV page.
3. The user will then get to select the rephrase/generated phrase they he or she desires. This will in turn refine the model in the backend, and make it better
4. After completing the choosing of bullet points, a CV can be generated, and the user can use that to apply to the company directly.

Future pipeline:
1. The user will be able upload their existing CV, cover letter, include stories, profile and their preferences, which will be stored in our backend. 
2. The backend automatically gives jobs that match based on all the information given
3. From there, the user chooses the job they want to start crafting a CV and cover letter for. 
4. The user will verify which are the headers, and which are the bullet points that need rephrasing. It will not violate the amount of space given for the bullet points.
5. At the CV stage, there will be an overarching goal, and the rephrasing will occur at the side of the existing CV bullet points. The newly generated bullet points will be on another panel 
6. The newly generated bullet points will use the following prompt to ensure that it will be well approved by the ATS checkers. It'll do so by checking with the backend what hasn't been ticked off yet in the CV, then knowing what to optimise towards, it'll rephrase it following the following prompt (and more if needed):
""" 
- Make it concise 
- Make it impactful 
- Make it sound good to a recruiter 
- Use British English.
- Optimise for getting approval from ATS checkers
- Ensure that it's optimised for [Fill this in with key skill it needs to be optimsed for]
"""

Current development roadmap:
The goal of this development cycle is to ensure that the rephraser, and bullet point generators are optimised.

1. If there are any missing fields in the keywords, skills, abilities, company description, or job description. Let the user be able to just copy and paste it so that the db gets updated with the most recent population. This will be the first step. Once the user is happy with what's inside the job description, the next rephraser can start to work. So we're economical with tokens. 
2. The backend will ingest this data. Identify what is missing from the current CV, and highlights using colours, whether a keyword/skill/ability has been actually included in the current CV or not
3. In the right hand side panel, for every main section. A few new lines are generated that would be optimised for what the CV is currently missing. e.g. In work experience, for the employer Jaguar TCS racing, it had about 9 lines in the CV, so it'll produce 5 new lines (roughly half) for the user to pick from that is optimised for the CV. This will be focused on drawing from the user's profile, and experience, so rather than just rephrasing what's already on the CV, it'll generate new points. There'll also be the option for me to add my own line in here. Then I can just drag and drop it into where I want to replace the line of my original CV.
4. The middle panel is the rephraser. This is where we optimise for character length, and ensuring that the line is rephrased to hit some or one of the requirements on the left hand panel. When clicking "rephrase", it'll show 3 alternative rephrases (generated from Claude Haiku). The user will click on their most desired line, or if not, they'll click regenerate, and it'll give another 3 rephrases.
5. Once the user is happy with the rephrasing. The user clicks generate CV, and the pipeline ends.

Notes: This has to be developed with scalability in mind. So the user has to be in the loop regarding system design decisions.