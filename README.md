# Masto-Feed RSS feed to Mastodon bridge
RSS feed reader that posts updates in Mastodon API. It also attends to mentions to perform some maintenance actions.

## Features

This bot is made with ❤️ from Düsseldorf and it is designed to read from user defined feeds and publish their posts through a single Mastodon bot account.

* **[Super detailed setup via a config files](#configuration-files)**: Take full control of the execution
* **[No DB is needed](#no-db-is-needed)**: Everything is done with files
* **[Interact with the bot](#interact-with-the-bot)**: The bot understands mentions with actions
* **[Feed URL discovery](#feed-url-discovery)**: The bot will discover the *Feed URL* from the given *Site URL*
* **[Anti-flood publishing](#anti-flood-publishing-be-kind)**: [Optional] Publish one post in every run from the queue
* **[Images supported](#images-support)**: Also publish the images that come with the original post.
* **[Exhaustive logging](#exhaustive-logging)**: Log everything that is happening in the run, so you can monitor what's going on
* **[Dry Run support](#dry-run)**: You can set it up and run it without any actual publishing until you're happy with the result
* **[Keep track of what is already captured](#keep-track-of-what-is-already-captured)**: To avoid repeating published posts!

### ⭐️  Configuration Files
A set of Yaml files in [the ´config´ directory](./config/) allows you to configure all possible options. All parameters come largely commented for easy understanding

Make sure you create your execution copy from them before you run the bot. For example, for the [main config file](./config/main.yaml.dist), run the following in the terminal from the repository's root directory:

```bash
cp config/main.yaml.dist config/main.yaml
```

### ⭐️  No DB is needed
Why to use an infrastructure that not necessarily comes for granted when everything can be achieved with files? This way you can easily monitor and adjust anyting quickly.

All state files are stored in the [repository's root `storage` directory](./storage/).

### ⭐️  Interact with the bot
The bot is listening for mentions. The basic CRUD actions are represented plus some more. Also, the writting actions can be allowed to a single *admin* account, and of course the answer will respect the visibility of the mention (mention it as *private* and it will answer in the same one).

Take a look at the functionality in the [Interacting with the bot](#interacting-with-the-bot) section.

### ⭐️  Feed URL discovery
Don't stress yourself trying to find the Feed url: just give the site URL and the bot will discover it for you.

### ⭐️  Anti-flood publishing: be kind
The bot is meant to be executed scheduled through a cron ideally every 15 or 30 minutes. In every run it gathers posts into a queue and is intended to publish only one post, the older first.

Why? The idea is to avoid flooding the *Local* timeline, having a large amount of posts coming out of nowhere. Be kind with your neighbours in your instance :-)

You can change this behaviour from [the config file](./configs/main.yaml.dist#L66) and simply publish everything queued in every run.

### ⭐️  Images support
The images that come with the Feed posts will be downloaded and re-upload to the published post, preserving any description that they could have.

### ⭐️  Exhaustive logging
A bot is somethig that executes in loneliness, so it's cool to have the work logged into a file with several logging degrees so that we can monitor how is it behaving. It also supports log rotation, stdout print and custom formatting.

### ⭐️  Dry Run
When setting up the bot you may want to avoid to publish the queue, while you're adjusting the parameters. With this Dry Run option it can run it to gather content and fill the queues without the fear of flooding your Mastodon account with test messages. [Here in the config file](./configs/main.yaml.dist#L63) you can control this option, that **comes activated by default**!

### ⭐️  Keep track of what is already captured
The bot registers every new content in every run, so that it avoids repeating the actions over the same items. This is useful as some sources mark an old post as new and other bots may re-publish it. 
As usual this can be turned off and repeat all processing for every content in every run, useful while developing.

## Interacting with the bot

These are the currently implemented actions that the bot will understand. In the examples here it is assumed that the mastodon account is `@feeder` and it is called from the same instance, otherwise don't forget to add the feeder's domain like `@feeder@social.arnaus.net`.

### 💬 *hello* command

This command is an initial help command that explains itself and enumerates the available commands.

for example:
```
@feeder hello
```

will return something like:
```
I am an RSS Feeder bot. You can use the following commands with me:

add [site-url] [alias] "name of the feed" -> Will register a new RSS
update [alias] [site-url] "name of the feed" -> Will change the URL for an alias
remove [alias] -> Will remove the record
test [site-url] -> Will test the URL searching for RSSs
list -> Will show all the records I have
```

### 💬 *list* command

This command lists the feeds currently registered.

for example:
```
@feeder list
```

will return something like
```
@xavi The registered Feeds are:

[xavi-blog] Xavi's Blog: https://xavier.arnaus.net/blog/ (https://xavier.arnaus.net/blog.rss)
[xkcd] xkcd: https://xkcd.com/ (https://xkcd.com/rss.xml)
```

### 💬 *test* command

This command tests a given *Site URL*, by running all validations and trying to find the *Feed URL* (RSS, Atom, ...) that will be used to gather the content.

for example:
```
@feeder test https://xkcd.com
```

will return something like
```
@xavi The site URL https://xkcd.com appears to have a valid feed at https://xkcd.com/rss.xml
```

When it's an invalid URL:
```
@feeder test wrong,net
```

will return something like
```
@xavi The given URL does not seem to be valid. Don't forget the schema.
```

When the feed URL could not be found:
```
@feeder test https://google.com
```

will return something like
```
@xavi I could not get a valid RSS feed from the given URL. Perhaps it is in a /blog subdirectory?
```