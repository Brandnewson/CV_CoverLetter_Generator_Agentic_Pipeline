# Experience Stories

Raw experiences for drafting new bullets when the bank doesn't have a good match.

## Jaguar TCS Racing

During the season I built a tool that let strategists model energy regeneration decay
across different brake bias settings. Used in real race weekends for in-lap decisions.
Built in Python with a Flask frontend. Main challenge was making it fast enough to run
live during a session with minimal latency.

Support the Vehicle Performance Group in the field of Strategy, Simulations & Software in the lean and fast-paced environment of Formula E. Developed full-stack web apps, custom libraries, data processing pipelines, and performed data analysis with the aim of increasing car performance. Combined programming (Python, ReactJS, MATLAB, VBA) with race engineering tools (ATLAS, WinTax, RaceWatch) to deliver validated insights, streamline performance analysis, and support real-time decision making on race weekends in the Vehicle Performance Group.

Worked within Jaguar TCS Racing’s Vehicle Performance Group across strategy, simulations, and software in the high-pressure, agile environment of Formula E. Developed and deployed bespoke full-stack web apps, Python data pipelines, and custom libraries to convert timing feeds into telemetry, optimise GPS data with KD-trees, and provide scalable tools still in use today. Built long-term maintainable software from a single Python script into a fully deployed application using object-oriented design patterns, robust error handling, and CI/CD pipelines to ensure reliability and scalability. Used MATLAB and ATLAS for tyre, energy, and battery modelling, validating simulations with telemetry to support data-driven race decisions. Performed competitor radio analysis across energy management, pit-stops, tyre strategy, battery, and vehicle setup, delivering concise per-session summaries to inform strategy. Repurposed and extended machine learning tools with CNNs and OpenCV to automate competitor video analysis, reducing manual workload and enabling engineers to focus on performance-critical tasks. Combined programming expertise (Python, React, MATLAB, VBA) with motorsport tools (WinTax, RaceWatch, ATLAS) to deliver actionable insights, streamline workflows, and directly contribute to performance optimisation, efficiency, and innovation.

Worked within Jaguar TCS Racing’s Vehicle Performance Group across race operations, simulations, and software in the high-pressure environment but lean nature of Formula E. Supported race execution through competitor radio analysis (energy management, pit stops, tyre strategy, battery, and vehicle setup), delivering concise session reports that directly informed strategy decisions. Processed simulator and telemetry data in MATLAB and ATLAS to model tyres, energy, and battery temperatures, validating simulations with live track data to guide race engineering choices. Developed and deployed bespoke Python pipelines and full-stack tools to convert timing feeds into telemetry, optimise GPS data with KD-trees for tow analysis, and provide validated insights under time-critical constraints. Built scalable, maintainable software from a single Python script into a fully deployed application with CI/CD pipelines, ensuring robustness and long-term usability. Repurposed machine learning tools with CNNs and OpenCV to automate competitor video analysis, reducing manual workload and enabling engineers to focus on performance-critical tasks. Combined programming expertise (Python, React, MATLAB, VBA) with motorsport platforms (WinTax, RaceWatch, ATLAS) to streamline workflows, enhance data-driven decision-making, and deliver measurable performance gains on race weekends.

- Incident-position correlation analysis
- Dockerise livetimingfeed
- Kubernetes Feasibility
- Deploying of docker images to ECS and ECR through azure devops pipeline
- RESS thermal simulations when boost charge was introduced
- Marshalling for track days
- Took over old codebase, understood, refactored, timing feed to atlas C# program
- Read through Sporting Regs to make a quiz, potentially finding loopholes
- Writing a python library for the team to interface with atlas, converting custom data to a format readable by Atlas
- Extract MongoDB data to custom data, to Atlas through Python
- Merged Multiple git repos into one
**Atlas_BT**

A library that holds
an atlas reader & writer function. Used by Data Science & Strategy and
Software. Based on ATLAS_MB. Guess what the BT stands for heh. AtlasReader_VSE
and AtlasWriter_VSE in Data Science has this as a dependency, which itself is a
dependency by 4 other Data Science Tools

**AKS_Timing_Feed_Service**

A trackside app that
lives in the trackside servers (uploaded via pipelines), that converts &
transforms timing feed data into atlas channels. My pride and joy. Don't hate
me for shitty code pls.

**Onboards_detection**

An image recognition
software that helps us clip dash & onboard footage videos (needs rework!).
Made by Enrique, added ability to recognise Onboards from me. Could do with a
refresh, and potentially using vision transformers for image recognition instead.

**AKS_Dashboard_WinTAXStream**

Script that streams
data from a CSV to the AKS_Dashboard. In WinTAX, there's a VBA script I wrote
that streams live wintax data to the CSV that this reads from.

**OpsRoom_ChronoTimer**

Runs in the ops room
over the race weekend, lets ops room have a view of time till next event,
current time, time at track, rain viewer widget, and an overview of the whole
day. My responsibility was to populate the config.js which had all the event
times then push to server using ./pushToServer.sh

**FIA_Decisions**

Simply queries a
page which has all the FIA Stewards decisions, collects the PDF in Sporting
Documents folder in OneDrive, and we parse all the pdf info into a collective
excel sheet, it runs semi-okay but sometimes we run into either parsing errors,
or OneDrive syncing errors. I run this from my computer despite what it says on
the readME due to some permissions thing with OneDrive.

Shared repos

**Strategy_Scripts**

Basically a bunch of
scripts that Roberta made in the past, and a few by me, and some by Jas. For
the Strategy Group to get some analysis done.

Scripts I had
responsibility of are:

- Strategy_ResetWinTaxCharge
    - Resets the "session energy charged" in the AKS_Dashboard widget
- Strategy_PitStopAnalysisV2
    - Made to analyse pit stop pace after London race (See strategy Report to London for more context)
- Strategy_PostSesEchoFormatter
    - echoFormatter.py
        - Converts the raw echo excel into a format where categorising of radio messages becomes really easy to do
    - postSesVidCombiner.py
        - If you've clipped a bunch of videos, pointing this script to a folder path, lets you merge all the vids in that folder
    - transcriptCombiner.py
        - This combines the text2Speech excels into an easily readable format. Needs updating as they're using hardcoded driver names, and teams for S12.

**RESS_Modelling**

A bunch of scripts
that lets us model what might happen to the RESS equity model during races or
do pre-race simulations.

Scripts I had
responsibility of are:

- Workbook/Canopy RMS APP Correlation V2
    - runDataCollection.m
        - This looks at a folder, and runs getATLASData on each ssn, then parses the desired data into the json file path you had pointed at.
    - plotCanopyAAPRMSCorrelation.m
        - This plots 3 plots
        - 1 lap AAP canopy track comparison
            - Compares expected 1 lap canopy RMCU AAP to actual data 1 lap canopy RMCU AAP
        - PBMS_RMS & RMCU_AAP correlation
            - Similar to above, but comparing the 4 min period itself, and seeing if there's a pattern to in-tow and no-tow RMS/AAP
        - Etyre vs AAP correlation (currently not working, requires adding Etyre to canopyDataConverter.m)
            - Checking the sensitivity of the existing RMS/AAP plots to tyre energy correlation
            - Just generally if there's trends of tyre energies to AAP over the course of different tracks
            - Show you trends that if you become tyre limited, you won't have to worry about AAP anymore etc
- Canopy/canopyDataConverter.m
    - Given canopy exports, it converts that data into .mat files for manipulation in Matlab
    - Note: if you notice the "tRun" metric, it's how much time has passed in the simulation world. We resample it at a rate of 10Hz, but it's actually not the most accurate way of doing things as tRun indicates the actual time being CLOSE to 10Hz, but not quite. Just so you're aware.
- Canopy Race Sim Sweeps
    - Not really used as much anymore as there's other ways of simulating what happens to the RESS over time, but it's a tool that sweeps tAmbient, lap we start clipping, what level of clipping, lap we pit boost, and then plot what happens to battery temperatures over the race
- Boost Charge Metrics
    - A script that looks at a directory (and subfolders), then gives you all sorts of boost charge metrics.
- BBW Penalty vs Clipping Sweeps
    - Script to check if the how much energy do you "burn" to the BBW at different levels of clipping

**OCR_TVEnergies**

Never touched the
code, but it's the image recognition software that runs trackside to tell
engineers when there's SOC shown on TV. Lais runs it over the weekend but you
might have to SSH into a trackside PC to run this if she's not free

**TPMS_Dashboard**

**AKS_Dashboard**

**StrategyTool**

In-house ReactJS web
apps that we might assist in developing for Tobee

**LiveTimingFeedServer**

**LiveTimingFeedProxy**

**LiveTimingFeedClient**

How we as a strategy
department streams timing feed data into our web clients

My responsibilities

Note that the
structure of the team is ever changing, your role might not be the same exact
as mine but this is what I used to do, so that you can better understand what
your role might be

**Factory Roles**

- Software Maintenance & Engineering
    - Web dev, matlab and python dev are generally what I was working on.
    - CI/CD work - pipelines, and essentially understanding what apps go where is another big thing
    - Those repos I was talking about earlier require someone to maintain if there's any issues.
- Data Analysis
    - Those AAP RMS plots are probably the main one I look at, but I basically had free reign to do whatever data analysis I wanted with the Timing Feed or Atlas
    - Tbh this was something I wished I had done more of, but you have access to so much Atlas data from our race cars, you can take a look at everything from Energy-saving, to how each driver is on the pedals (steering wheel. Quite a lot you can do, but I spent more of time developing software than doing this. Ultimately depends on what's important for the team at the time.
- Tobee's bi***
    - I'm joking, but we do work with Tobee as our boss a lot because he has visibility of everything that happens from a software engineering and strategy POV in Performance as the Senior Strategy and Software Engineer. I often just ask him for direction to see if what I'm working/intending to work on makes sense.

**Race Weekend Roles**

- Pre-Race
    - Video editing
        - Overtaking videos, Attack loss videos, overtakeability analysis
    - AAP correlation
        - Running the RESS_Modelling scripts to see the past season's data, compared to Canopy expectations
    - Track map editing
        - A track map is usually sent in a kml format by the organisers, but sometimes we don't have that, and hence we have to manually edit it directly in Google Earth Pro for example when they changed the circuit in Jeddah, or in Tokyo
        - Track map itself is used in RaceWatch
        - This is sent to Canopy, which converts it into a trajectory which can be used for a racing line in Racewatch and a few other tools in Software & Strategy
- Race
    - Video Clipping
        - Incidents happen with cars in FE all the time, we clip the point in which they happen to ours cars so we can bring it up to the FIA stewards.
    - Radio Analysis
        - Keep track of all that's coming through echo, and inform ops room (I was informing Alex) of any interesting information
        - Also take note of what might be interesting over the session, so you can do a post-session analysis/summary in the event OneNote
    - Head of ghost ops
        - This is a role bestowed upon me by Alex Pedley when he was the ops room lead, the point of contact is between him and me as Rule of 6 disallows any more people than the ops room assisting in performance.
        - Ensure everyone in ghost ops is taken care of, delegate tasks accordingly, and pay attention to what might be needed by the race team that the ghost ops can help with.
    - RaceWatch
        - You'll likely take over my RW license, in which you get to see what's happening live, and hence build a better picture of what's happening in the race
- Post-race
    - Radio transcriptions
        - Listen in to all the drivers, transcribe each of them, then summarise
    - RMS AAP Scripts
        - Post-race, get the AAP and RMS scripts down so it can be used for canopy correlation

Firstly, I thrive in high-pressure environments with challenging deadlines and enjoy applying engineering fundamentals to new problems. During Formula E Season 11 with Jaguar, we faced significant changes, including new tires and four-wheel drive in attack mode. The team was looking for failsafe contingencies along with a desire to unlock performance in the tyre. I stepped up by suggesting developing a new in-house tool on the race weekend itself that let me combine my mechanical engineering foundation I picked up from my diploma with my coding skills from computer science to develop an in-house MATLAB coding tool that quantified the friction-brake energy required to raise tyre core temperatures without compromising battery strategy. I validated this new tool against race telemetry and presented clear findings that supported strategy decisions, contributing to holding off Porsche in P2, ultimately securing a win at Shanghai Race 2. This experience showcased my ability to turn an engineering challenge into an immediately operational and robust internal tool that still lives in Jaguar to this day using the marriage of my diverse skillset.

Lastly, my curiosity to explore beyond my comfort zone drives my continuous growth. At Jaguar, I regularly engaged with colleagues across departments to understand their challenges, which led me to uncover an unused repository that once identified onboard clips from YouTube streams. Realising the potential, I set out to repurpose and extend the tool to include the ability to recognise dashes which contained key competitor data such as tyre pressures, which was needed by the tyre department. Despite having no prior experience in machine learning, I studied the fundamentals of the existing CNN classifier and sourced my own dataset. The innovation eased a major manual burden, freeing engineers to focus on performance-critical tasks. By taking initiative, I turned curiosity into measurable performance gains. This ability to work independently and a continual desire to learn about new technology, language features and frameworks aligns well with the role of Junior Data Analysis and Visualisation Engineer. 


I am a dedicated team player who knows when to work independently and when to seek input from others to achieve the 
best outcome. At Jaguar Racing, the compact team structure meant that responsibilities overlapped, requiring me to contribute 
simultaneously across simulations, software, and strategy. When developing a Python-based data pipeline converting raw Alkamel 
Timing Feed data from a noSQL database into telemetry channels, instead of developing in isolation, I sought feedback from the 
Vehicle Performance Group to ensure channels stayed relevant. I collaborated with software engineers to design the CI/CD 
architecture. I sought advice through code reviews with senior engineers for long-term scalability in object-oriented programming 
using design patterns, modularity, and extensive error handling. I also aligned with strategists to ensure the outputs had direct race 
impact. This balance of independence and collaboration turned what began as a single Python file into a fully functioning application 
still powering performance at Jaguar today. The experience reinforced my ability to thrive in multidisciplinary environments, 
translating user needs across the business into scalable software tools that allow for continuous improvement, an approach directly 
suited to being a Graduate Software Engineer in the Vehicle Performance Group. 

## Formula Student

Led the performance sim sub-team from scratch. No simulation infrastructure existed when
I joined. Built the entire lap time sim over ~3 months using Milliken & Milliken for the
tyre model and aerodynamic drag from F1 technical papers.

Secondly, I excel at working across a diverse group of engineers to collaborate and discover well-rounded solutions. At Leeds Gryphon Racing, there was an issue where a new ECU and data acquisition system meant that the electrics team were not aware of what sensors to put on the car and what channel strategies to use. On the other hand, the vehicle dynamics team were struggling with validating their design choices. Realising the potential for performance to be extracted and simulations to provide first-principle-derived evidence of choice, a meeting was held to bridge the gap between the leads. Through communicating each team’s requirements and issues, we managed to conclude that GPS sensors and wheel speed sensors were critical to helping us correlate our tyre models alongside the sampling rates, logging strategies, and channel strategies, which in turn provided the performance metrics in the correct format that the vehicle dynamics team desired from simulations. This balance of collaboration and high-level oversight turned what began as confusion and a dilemma into a key decision for the team’s vehicle data architecture that will aid performance gains for years to come, crucial to being a software engineer that can translate technical information to diverse audiences.


## Aerodynamic idea RAG analyser
Junior aerodynamicists understand core principles but struggle to translate them into novel designs. Senior engineers hold valuable expertise, yet this knowledge remains inaccessible to those starting their careers.
AeroInsight bridges this gap through Retrieval-Augmented Generation. When a user submits an aerodynamic concept, the system converts the description into a mathematical vector using a neural embedding model. This vector represents the semantic meaning of the concept in 384-dimensional space. The system then searches a vector database containing 31,652 chunks from 248 research papers, retrieving the most semantically similar passages based on cosine similarity scores.
These retrieved passages form the context for a large language model evaluation. GPT-4o analyses the concept against the retrieved literature, assessing novelty by identifying precedents and measuring how the proposed design differs from established approaches. The model outputs structured evaluations including novelty scores, confidence levels, underlying aerodynamic mechanisms, engineering trade-offs, and regulatory considerations. Every evaluation includes citations linking back to the original arXiv papers, ensuring traceability and academic rigour.
The tool is callable through two interfaces. Engineers can use the web dashboard for visual concept management and evaluation review. Alternatively, the system exposes an MCP server, allowing AI agents like Claude or GitHub Copilot to create concepts, trigger evaluations, and retrieve results programmatically. This agent-native design enables automated workflows where users can conversationally explore aerodynamic ideas without switching contexts.
Whether working on Formula One development or Formula Student projects, engineers gain immediate access to research-backed insights. They discover what constitutes genuine novelty, identify proven implementations, and understand practical trade-offs before committing resources to physical prototyping.
The AeroInsight project follows a hexagonal (ports and adapters) architecture pattern that isolates business logic from infrastructure concerns. The codebase is organised into distinct layers: domain models define the core business entities, services encapsulate the RAG pipeline logic, infrastructure handles database and API integrations, and API routes expose functionality through HTTP endpoints. This separation allows the same business logic to be consumed by multiple interfaces (REST API and MCP tool server) without modification.
The design embraces the principle that the core RAG evaluation pipeline should not depend on how it is accessed. The rag_service.py module contains pure business logic that operates on domain objects, whilst the api/evaluations.py routes and mcp/tool_service.py adapter merely transform these domain objects into their respective protocol formats. This approach enables straightforward testing of evaluation logic in isolation and makes it trivial to add new client interfaces later.

