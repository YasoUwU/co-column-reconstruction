# NASA Earthdata access

MERRA-2 and MOPITT downloads require a free, personal NASA Earthdata Login account. This
repository does not provide an account, username, password or access token.

## 1. Create and activate an account

1. Open the official [Earthdata registration guide](https://urs.earthdata.nasa.gov/documentation/for_users/how_to_register).
2. Select the registration option and create your own profile.
3. Open the activation email from NASA and activate the account before attempting a download.
4. Sign in to [Earthdata Login](https://urs.earthdata.nasa.gov/users) and accept any provider
   authorization requested for the relevant NASA data centre.

A standard user-level account is sufficient for downloads supported by Earthdata Login.

## 2. Configure credentials locally

Keep credentials outside this repository. Use one of the supported local mechanisms:

- a protected `.netrc` file in your user home directory;
- `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` environment variables for the current session;
- an interactive masked password prompt when offered by the acquisition tool.

Never place a username, password or token in source code, configuration YAML, notebooks,
terminal command arguments, logs or screenshots. Never commit `.netrc` or local environment
files. Every collaborator must use their own Earthdata account.

## 3. Verify access

Test access with a single requested file before starting a multi-year download. If access is
denied, confirm that the account is activated and that the relevant data-provider application
has been authorized in the Earthdata profile. Do not disable TLS verification or copy another
person's credentials to work around an authorization error.
