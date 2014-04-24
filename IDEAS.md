## Ideas

### Export

- Export all as JSON / GeoJSON
  - Background task?
  - preemptively cache?
  - no longer necessary with Moves own [export](https://accounts.moves-app.com/signin/export)?

### Geography

- ~~Make sure timestamps are recorded in LineStrings~~
- Calculate trackpoint speeds not just segment averages (geopy?)
- Hook up to external elevation service

### Maps

- Display multiple days on map
  - useful if we have all the export cached (and vice versa)
- Cycle through activities (like the app, cough)

### Sharing

- Permanent (ie per user) URLs
  - only last until Memcache timeout?
  - require a real DB to record which days are shared?
- Push GeoJSON to private [gist](http://gist.github.com/)
- Use gist URL to link to [geojson.io](http://geojson.io/)

### Cross-service

- last.fm
- flickr
- (anything with a datestamp but no native geo)

### Activity

- Transport (sums aren't calculated by Moves)
- Cumulative for month / year
  - to-date months/years not to-first
  - extrapolations
- Sort lists by most active day
- Charts (how to make them interesting though)

### Other

- Ask people who actually work out what they want
- Ditto cyclists
- Better debugging?

