 I added some files under @backend/ folder
  @backend/.env contains Google and OpenAI keys. Use the Google API key to run job fit comparison.
  @"Gopal Cheruku Resume.docx": Use this as a resume to compare against the job description and generate a match score
  @backend/secrets/: This folder contains @backend/secrets/credentials.json and @backend/secrets/token.json to access my Google mail.
  My Google mail contains a label 'Job alerts' that contain job alerts from Dice, LinkedIn, Glassdoor, and Indeed
  With this information do the following:
  1. Write a background task that is automatically executed every 4 hours
  2. The task fetches the latest alerts from my Google mail that contain the label 'Job alerts' and extracts job information
  3. Using the latest discovery timestamp of the job alerts in the database, fetch the alerts that were deliver later.
  4. Save the latest fetch timestamp so it can be used in the next run.
  5. Check for the job description link if it already exists in the database since some alerts are resent
  6. Create a way (a button maybe) in the UI to manually fetch the latest alerts from gmail