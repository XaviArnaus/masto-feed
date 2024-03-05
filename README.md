# Masto-Feed RSS feed to Mastodon bridge
RSS feed reader that posts updates in Mastodon API. It also attends to mentions to perform some maintenance actions.

## ✅ Features

This bot is made with ❤️ from Düsseldorf and it is designed to read from user defined feeds and publish their posts through a single Mastodon bot account.

* **[Super detailed setup via a config files](#%EF%B8%8F--configuration-files)**: Take full control of the execution
* **[No DB is needed](#%EF%B8%8F--no-db-is-needed)**: Everything is done with files
* **[Interact with the bot](#%EF%B8%8F--interact-with-the-bot)**: The bot understands mentions with actions
* **[Feed URL discovery](#%EF%B8%8F--feed-url-discovery)**: The bot will discover the *Feed URL* from the given *Site URL*
* **[Anti-flood publishing](#%EF%B8%8F--anti-flood-publishing-be-kind)**: [Optional] Publish one post in every run from the queue
* **[Images supported](#%EF%B8%8F--images-support)**: Also publish the images that come with the original post.
* **[Exhaustive logging](#%EF%B8%8F--exhaustive-logging)**: Log everything that is happening in the run, so you can monitor what's going on
* **[Dry Run support](#%EF%B8%8F--dry-run)**: You can set it up and run it without any actual publishing until you're happy with the result
* **[Keep track of what is already captured](#%EF%B8%8F--keep-track-of-what-is-already-captured)**: To avoid repeating published posts!

### ⭐️  Configuration Files
A set of Yaml files in [the `config` directory](./config/) allows you to configure all possible options. All parameters come largely commented for easy understanding

Make sure you create your execution copy from them before you run the bot. For example, for the [main config file](./config/main.yaml.dist), run the following in the terminal from the repository's root directory:

```bash
cp config/main.yaml.dist config/main.yaml
```

### ⭐️  No DB is needed
Why to use an infrastructure that not necessarily comes for granted when everything can be achieved with files? This way you can easily monitor and adjust anyting quickly.

All state files are stored in the [repository's root `storage` directory](./storage/).

### ⭐️  Interact with the bot
The bot is listening for mentions. The basic CRUD actions are represented plus some more. Also, the writting actions can be allowed to a single *admin* account, and of course the answer will respect the visibility of the mention (mention it as *private* and it will answer in the same one).

Take a look at the functionality in the [Interacting with the bot](#-interacting-with-the-bot) section.

### ⭐️  Feed URL discovery
Don't stress yourself trying to find the Feed url: just give the site URL and the bot will discover it for you.

### ⭐️  Anti-flood publishing: be kind
The bot is meant to be executed scheduled through a cron ideally every 15 or 30 minutes. In every run it gathers posts into a queue and is intended to publish only one post, the older first.

Why? The idea is to avoid flooding the *Local* timeline, having a large amount of posts coming out of nowhere. Be kind with your neighbours in your instance :-)

You can change this behaviour from [the config file](./config/main.yaml.dist#L66) and simply publish everything queued in every run.

### ⭐️  Images support
The images that come with the Feed posts will be downloaded and re-upload to the published post, preserving any description that they could have.

### ⭐️  Exhaustive logging
A bot is somethig that executes in loneliness, so it's cool to have the work logged into a file with several logging degrees so that we can monitor how is it behaving. It also supports log rotation, stdout print and custom formatting.

### ⭐️  Dry Run
When setting up the bot you may want to avoid to publish the queue, while you're adjusting the parameters. With this Dry Run option it can run it to gather content and fill the queues without the fear of flooding your Mastodon account with test messages. [Here in the config file](./config/main.yaml.dist#L63) you can control this option, that **comes activated by default**!

### ⭐️  Keep track of what is already captured
The bot registers every new content in every run, so that it avoids repeating the actions over the same items. This is useful as some sources mark an old post as new and other bots may re-publish it. 
As usual this can be turned off and repeat all processing for every content in every run, useful while developing.

## ✅ Interacting with the bot

The current implemented commands are. Visit [the commands documentation](./docs/commands.md) to get a full explanation of each one.

### 💬 *hello*
This command is an initial help command that explains itself and enumerates the available commands.

### 💬 *list*

This command lists the feeds currently registered.

### 💬 *test*

This command tests a given *Site URL*, by running all validations and trying to find the *Feed URL* (RSS, Atom, ...) that will be used to gather the content.

### 💬 *add*

This command adds a given *Site URL* into the records, so the content will be gathered and processed.

### 💬 *update*

This command updates an existing record's parameters. The only parameter that can't be changed is the `alias`, at it works as ID. All given values will overwrite the previous ones.

### 💬 *remove*

This command deletes an existing record.

## ✅ How to install it

This bot has 2 main executors: the main one intended to be run by the system's `crontab`, and the streaming listener that should run in the background attending the user's requests in their mentions.

It is a bot that is managed by Poetry, so the virtual environment and dependencies are nicely managed.

### 0️⃣ Clone the repository

Open a terminal to the host that will run this bot and clone this repository there. At this point, the bot is not yet versioned so the `main` branch will work.

```bash
git clone git@github.com:XaviArnaus/masto-feed.git .
```

### 1️⃣ Install Poetry

In the terminal to the host, install Poetry through the official installer

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Keep in mind that Poetry needs `python`, and this is actually a `Python 3` program. Alternativelly you can install Poetry with other strategies, just visit the [Poetry official documentation](https://python-poetry.org/docs/)

### 2️⃣ Initialise the project with Poetry

Now that we have Poetry and the bot's code, let's generate the Python's virtual environment and install the dependencies. 
Make sure that you're in the cloned project's directory and run:

```bash
poetry install
```

### 3️⃣ Set up the Fediverse account for the bot

This bot is meant to use a Fediverse account to publish the posts it discovers through the RSS feeds. This mean that you need to have an account set up for accessing it programatically.

For a Mastodon account, you need to go to your *Preferences* > *Development* and create a *New application*. It will generate a set of hashes.

### 4️⃣ Set up the bot configuration

The bot is set up by parameters in the config files. These config files live in the `config` directory. You only need to rename every `*.yaml.dist` file to `*.yaml`, edit it and configure the parameters inside.

The config files we have now are:
- [`main.yaml`](./config/main.yaml.dist): The main configuration file. It contains the Application main info, the Logging configuration, the Janitor connection set up, the queue file definition and the publisher configuration.
- [`mastodon.yaml`](./config/mastodon.yaml.dist): The mastodon configuration file. This bot understands profiles, so we have here the *default* profile and the *test* profile, that will be used for testing purposes.
- [`feed_parser.yaml`](./config/feed_parser.yaml.dist): The overarching configuration for the feeds to be parsed. At this point the feeds are not really configurable independently and use this configuration globally. In future versions this will be more coherent.

### 5️⃣ Start the listener

This bot is listening for the mentions that the configured fediverse account receives. In the configuration we set up the credentials so the bridge is created, we only need to start the background program that will behave with the mentions.

This bot has a command line application to manage all of this. Once you're placed at the root of the cloned project, you can run the following command:

```bash
bin/mastofeed streaming start
```

and it will start a background process that runs the streaming listener. That's all.

### 6️⃣ Running the bot by the `crontab`

A part from the "always running" listener in the previous point, the bot needs to run periodically to perform the tasks of gathering the possible new content and publish it through the Fediverse account. The easiest way is to set it up inside the crontab.

Open the `crontab` with your favourite editor:

```bash
crontab -e
```

... and add a line to run the cron, configuring also its schedule. for example:
```
12,27,43,57 * * * * cd /home/xavier/bots/social-arnaus-feeder && PATH=$PATH:/home/xavier/.local/bin bin/mastofeed feed run
```

Let's explain it per parts:
- `12,27,43,57 * * * *`: This is setting up the periodicity of the bot to run. Here it says "every day, every hour, at minutes 12, 27, 43 and 57.
- `cd /home/user/bots/masto-feed && PATH=$PATH:/home/user/.local/bin bin/mastofeed feed run`: This is literally: first move yourself to the directory `/home/user/bots/masto-feed`. Then with the PATH `$PATH:/home/user/.local/bin` please run the command `bin/mastofeed feed run`. This is done like this because when running commands in `crontab` the PATH is not carried on in the environment variables, so Poetry is usually not found and the run may fail.

### 🆒 And that's it!

At thi point we should have the bot running periodically, and the listener ready to get mentions and behave!

We can monitor the running of the bot by checking the logs that it produces:

```bash
tail -f log/masto-feed.log
```

The streaming listener also produces logs whenever a mention comes and also with any issue it may happen:

```bash
tail -f log/listen_in_background.log
```

I also recommend to check the possible commands that the CLI has, that helps to debug issues and ensure that the parameters are well set up:

```bash
bin/mastofeed commands
```