"""Auto Clip: long video in, captioned vertical shorts out, optionally posted to YouTube on a schedule with nobody pressing anything.

  intake    an uploaded file, or a link (Twitch, Kick, direct files; YouTube only as far as YouTube lets a download through)
  pick      the loudest, most active stretches; with a transcript the cut is moved to a sentence edge, and your AI crew writes the title
  cut       ffmpeg: 9:16, blurred-fill / zoomed / fill layout, burned-in captions when there is a transcript
  youtube   YouTube's own upload API with YOUR Google login and YOUR Google Cloud client: no cookies, no scraping, no third-party exe
  autopilot a small scheduler: daily cap, minimum gap, posting hours, review-first or fully automatic, a pause switch, a watch list of channels

Everything that posts is OFF until you turn it on, and nothing posts until you have said you own the video or have permission to clip it.
"""
