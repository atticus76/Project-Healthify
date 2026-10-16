# Sprint x Report

Video Link: (YT LINK)

## What's New (User Facing)

- Device Connection
- Dashboard UI
- Telemetry Emulator
- Login page

## Work Summary (Developer Facing)

For this sprint, we worked on four features: the dashboard UI, the device connection, our telemetry emulator and the login page. The dashboard page involved creating the basic Reflex components (analogous to the more typical React components in Typescript and Javascript; in fact a Python Reflex application is compiled into Typescript, though we elected to code our application in Reflex entirely in Python for simplicity), the pages and states behind those pages, and separating those entities into meaningful divisions. For our device connection functionality, we created a Google Cloud project so that we could connect to the Google Health API with a Google Account associated with a Fitbit (our chosen wearable device for this project, though we may end up connecting more devices), as well as a basic Python script to set up the proper OAuth 2.0 consents for our project to be registered as a client and pull data from the Google account associated with that Fitbit. Our current implementation should provide support for multiple users (more specifically, for users who are registered as test members on our Google project, which currently only includes us four developers), however until we set up our database, there is currently no way to persist this user information between application runs. Finally, we set up a telemetry emulator which could provide some basic JSON formatted data for health telemetry in case we were unable to set up our wearable device to send data to our application (luckily we have been successful so far). We were not able to complete the login page in this sprint, and plan to delegate it, as well as support for multiple users to the next sprint.

## Unfinished Work

For this sprint, we were unable to complete the user interface and backend business logic for the login page. In the next sprint, we plan to set up at least a basic functioning login/sign up page which potentially uses some sort of encryption for usernames and passwords connected to a database of users and their associated information. This will allow us to persist information about users, including their data, associated wearable provider accounts and devices, and other in-app preferences.

Additionally, while we are very happy with our first attempts for our other three issues (the telemetry emulator, a connection to our chosen wearable device, and the dashboard user interface), we have not yet moved them into the complete column of our Kanban board, as there are still aspects of these issues that need to be completed.

## Completed Issues/User Stories

Here are links to the issues that we completed in this sprint:

- [Device connection](https://github.com/atticus76/Project-Healthify/issues/1)
- [Dashboard UI](https://github.com/atticus76/Project-Healthify/issues/4)
- [Telemetry Emulator](https://github.com/atticus76/Project-Healthify/issues/10)

## Incomplete Issues/User Stories

Here are links to issues we worked on but did not complete in this sprint:

- [Login page](https://github.com/atticus76/Project-Healthify/issues/2) – due to time constraints and the workload of other issues, we were not able to get to this issue in this sprint. However, we believe we have a solid working prototype for our application, and that the login screen actually fits in better to the workload we would like to tackle in sprint two, which centers around persisting user data user some kind of database, likely some kind of RDS like Postgres with Supabase.

## Code Files for Review

Please review the following code files, which were actively developed during this
sprint, for quality:

- [healthify.py](https://github.com/atticus76/Project-Healthify/blob/main/code/frontend/healthify/healthify.py)
  _[telemetry_emulator](https://github.com/atticus76/Project-Healthify/blob/main/code/backend/telemetry_emulator.py)
  _[profile_controller.py](https://github.com/atticus76/Project-Healthify/blob/main/code/backend/profile_controller.py)
- [token_store.py](https://github.com/atticus76/Project-Healthify/blob/main/code/backend/token_store.py)
  _[google_health.py](https://github.com/atticus76/Project-Healthify/blob/main/code/backend/google_health.py)
  _[google_oauth.py](https://github.com/atticus76/Project-Healthify/blob/main/code/backend/google_oauth.py)

## Retrospective Summary

Here's what went well:

- Fitbit device connection
- Emulator Implementation
- Dashboard UI

Here's what we'd like to improve:

- Setting up Postgres for multiple users
- Dashboard UI additional information and dynamics (telemetry, graphs, etc.)
- Device connection should be to other devices too.

Here are the changes we plan to implement in the next sprint:

- Instead of calculations, we want to retrieve results from databases when getting personal information using a free online API ([MyPlate](https://myplate.food/api))
- Data storage (likely Supabase or something similar)
- Backend Databases for users, devices, and telemetry records
- Polishing more of the main functionalities
