## Interacting with the bot

These are the currently implemented actions that the bot will understand. In the examples here it is assumed that the mastodon account is `@feeder` and it is called from the same instance, otherwise don't forget to add the feeder's domain like `@feeder@social.arnaus.net`.

### 💬 *hello* command

This command is an initial help command that explains itself and enumerates the available commands.

🔵 The blueprint is:
```
hello
```

🟢 for example:
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

🔵 The blueprint is:
```
list
```

🟢 for example:
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

🔵 The blueprint is:
```
test [site-url]
```

where:
- `site-url` is the *Site URL*. The bot will attempt to discover the *Feed URL* from it


🟢 for example:
```
@feeder test https://xkcd.com
```

will return something like
```
@xavi The site URL https://xkcd.com appears to have a valid feed at https://xkcd.com/rss.xml
```

🔴 When it's an invalid URL:
```
@feeder test wrong,net
```

will return something like
```
@xavi The given URL does not seem to be valid. Don't forget the schema.
```

🔴 When the feed URL could not be found:
```
@feeder test https://google.com
```

will return something like
```
@xavi I could not get a valid RSS feed from the given URL. Perhaps it is in a /blog subdirectory?
```

🔴 When the URL is missing:
```
@feeder test
```

will return something like
```
@xavi Seems like you forgot parameters
```

### 💬 *add* command

This command adds a given *Site URL* into the records, so the content will be gathered and processed.

🔵 The blueprint is:
```
add [site-url] [alias] "name of the feed"
```

where:
- `site-url` is the *Site URL*. The bot will attempt to discover the *Feed URL* from it, just like the *test* command.
- `alias` is the internal identifier to be assigned. It allows only letters, numbers and hypens. It's optional. If not given, it will slugify the feed URL. It is not visible, only used for commands.
- `"name of the feed"`: It's the name that this feed will have, to be shown in every published post. It's optional. If not given, it will take the `alias`


🟢 for example, a minimal call:
```
@feeder add https://xkcd.com
```

will return something like
```
@xavi Added
```

and will be using the following values:
- `alias`: `https-xkcd-com-rss-xml`
- `"name of the feed"`: `https-xkcd-com-rss-xml`

🟢 for example, another minimal call:
```
@feeder add https://xkcd.com xkcd
```

will return something like
```
@xavi Added
```

and will be using the following values:
- `alias`: `xkcd`
- `"name of the feed"`: `xkcd`

🟢 for example, a complete call:
```
@feeder add https://xkcd.com xkcd "XKCD blog"
```

will return something like
```
@xavi Added
```

and will be using the following values:
- `alias`: `xkcd`
- `"name of the feed"`: `XKCD blog`

🔴 When it's an invalid URL:
```
@feeder add wrong,net
```

will return something like
```
@xavi The given URL does not seem to be valid. Don't forget the schema.
```

🔴 When the feed URL could not be found:
```
@feeder add https://google.com
```

will return something like
```
@xavi I could not get a valid RSS feed from the given URL. Perhaps it is in a /blog subdirectory?
```

🔴 When the alias already exists:
```
@feeder add https://google.com xkcd
```

will return something like
```
@xavi The alias is already taken
```

🔴 When the parameters are missing:
```
@feeder add
```

will return something like
```
@xavi Seems like you forgot parameters
```

### 💬 *update* command
This command updates an existing record's parameters. The only parameter that can't be changed is the `alias`, at it works as ID. All given values will overwrite the previous ones.

🔵 The blueprint is:
```
update [alias] [site-url] "name of the feed"
```

where:
- `alias` is the internal identifier to be related. It must exists. Use the *list* command first to see all aliases.
- `site-url` is the *Site URL*. The bot will attempt to discover the *Feed URL* from it, just like the *test* command.
- `"name of the feed"`: It's the name that this feed will have, to be shown in every published post. It's optional. If not given, it will take the `alias`


🟢 for example:
```
@feeder update xkcd https://xkcd.com
```

will return something like
```
@xavi Updated
```

and will be using the following values:
- `"name of the feed"`: `xkcd`

🟢 for example, a complete call:
```
@feeder update xkcd https://xkcd.com "XKCD blog"
```

will return something like
```
@xavi Updated
```

and will be using the following values:
- `alias`: `xkcd`
- `"name of the feed"`: `XKCD blog`

🔴 When it's an invalid URL:
```
@feeder update xkcd wrong,net
```

will return something like
```
@xavi The given URL does not seem to be valid. Don't forget the schema.
```

🔴 When the feed URL could not be found:
```
@feeder update xkcd https://google.com
```

will return something like
```
@xavi I could not get a valid RSS feed from the given URL. Perhaps it is in a /blog subdirectory?
```

🔴 When the alias does not exist:
```
@feeder update unknown-alias https://xkcd.com
```

will return something like
```
@xavi I can't find that Alias in my records
```

🔴 When the parameters are missing:
```
@feeder update
```

will return something like
```
@xavi Seems like you forgot parameters
```

### 💬 *remove* command

This command deletes an existing record.

🔵 The blueprint is:
```
remove [alias]
```

where:
- `alias` is the internal identifier to be related. It must exists. Use the *list* command first to see all aliases.

🟢 for example:
```
@feeder remove xkcd
```

will return something like
```
@xavi Removed
```

🔴 When the alias does not exist:
```
@feeder remove unknown-alias
```

will return something like
```
@xavi I can't find that Alias in my records
```

🔴 When the alias is missing:
```
@feeder remove
```

will return something like
```
@xavi Seems like you forgot parameters
```