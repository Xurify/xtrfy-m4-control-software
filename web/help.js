// Help topics, written from Xtrfy's M4 Wireless quick-start guide (2021-12-06). Images are pages of that guide.
window.HELP = [
  {
    group: "Getting started",
    topics: [
      {
        id: "setup", title: "Connect the mouse", img: "setup",
        lead: "The M4 works wirelessly through its receiver, or wired with the USB cable.",
        steps: [
          "Plug the USB cable into your computer.",
          "Push the wireless receiver into the adapter on the other end of the cable. Keeping the receiver on the cable, close to your mousepad, gives the most stable signal.",
          "Slide the switch on the bottom of the mouse out of OFF to turn it on.",
        ],
      },
      {
        id: "switch", title: "The switch on the bottom", img: "power",
        lead: "The four-position switch underneath turns the mouse on and decides what the small button behind the scroll wheel does.",
        list: [
          ["OFF", "Mouse is off."],
          ["CPI", "The top button cycles through your DPI stages."],
          ["RGB", "The top button changes lighting effects instead."],
          ["PGDN", "The top button acts as the Page Down key."],
        ],
        link: ["buttons", "Change button assignments"],
      },
      {
        id: "charging", title: "Charging", img: "charging",
        lead: "Plug the cable straight into the mouse to charge it. You can keep using it while it charges.",
        list: [["Red light", "Battery is low."], ["Orange light", "Charging. With the RGB turned off, it shows as a short blink about once a second."], ["Your lighting", "Fully charged."]],
        note: "Xtrfy says to charge only from a computer's USB port, not a wall charger.",
        link: ["power", "See battery level"],
      },
      {
        id: "battery", title: "Check the battery on the mouse", img: "battery",
        lead: "Hold the buttons highlighted in the picture for 3 seconds. The light shows the charge level:",
        dots: [["#ef4444", "0–25%"], ["#f97316", "26–50%"], ["#eab308", "51–75%"], ["#22c55e", "76–100%"]],
        note: "This app also shows the exact percentage in the sidebar.",
      },
    ],
  },
  {
    group: "Settings on the mouse",
    topics: [
      {
        id: "cpi", title: "DPI (CPI) stages", img: "cpi-polling",
        lead: "With the bottom switch on CPI, press the button behind the wheel to step through the DPI stages. The light shows which stage you're on:",
        dots: [["#ef4444", "400"], ["#eab308", "800"], ["#f97316", "1200"], ["#3b82f6", "1600"], ["#a855f7", "3200"], ["#22d3ee", "4000"], ["#22c55e", "7200"], ["#ffffff", "19000"]],
        note: "These are the factory values. In this app you can change each stage's DPI and colour, and how many stages the button cycles through.",
        link: ["performance", "Edit DPI stages"],
      },
      {
        id: "polling", title: "Polling rate", img: "cpi-polling",
        lead: "Press the PR button on the bottom of the mouse to switch polling rate. The light shows the new rate:",
        dots: [["#ef4444", "125 Hz"], ["#3b82f6", "500 Hz"], ["#22c55e", "1000 Hz"]],
        note: "This app can also set 250 Hz.",
        link: ["performance", "Set polling rate"],
      },
      {
        id: "liftoff", title: "Lift-off distance", img: "liftoff",
        lead: "Hold the buttons highlighted in the picture for 3 seconds to switch lift-off distance.",
        dots: [["#ef4444", "1 mm"], ["#3b82f6", "2 mm"]],
        link: ["performance", "Set lift-off distance"],
      },
      {
        id: "debounce", title: "Click debounce", img: "debounce",
        lead: "Hold the buttons highlighted in the picture for 5 seconds to step through debounce times.",
        dots: [["#ef4444", "2 ms"], ["#3b82f6", "4 ms"], ["#22c55e", "8 ms"], ["#a855f7", "12 ms"]],
        note: "In this app you can pick any value from 0 to 30 ms.",
        link: ["performance", "Set debounce"],
      },
      {
        id: "reset", title: "Factory reset", img: "reset",
        lead: "Hold the buttons highlighted in the picture for 5 seconds to reset the mouse to Xtrfy's factory settings.",
        note: "The Reset & backup page in this app does the same over the cable, and can also bring back the exact settings your mouse had before this app changed them.",
        link: ["reset", "Open Reset & backup"],
      },
    ],
  },
  {
    group: "Lighting",
    topics: [
      {
        id: "rgb-effects", title: "Change lighting effect", img: "rgb-effects",
        lead: "With the bottom switch on RGB, press the button behind the wheel to cycle through lighting effects.",
        link: ["lighting", "Choose an effect"],
      },
      {
        id: "rgb-colour", title: "Change lighting colour", img: "rgb-colour",
        lead: "With the switch on RGB, use the button highlighted in the picture to step through colours.",
        link: ["lighting", "Pick a colour"],
      },
      {
        id: "brightness", title: "Brightness", img: "brightness",
        lead: "With the switch on RGB, use the side buttons together with the button shown in the picture: the front side button brightens, the back one dims.",
        link: ["lighting", "Set brightness"],
      },
      {
        id: "speed", title: "Effect speed", img: "speed",
        lead: "With the switch on RGB, use the buttons highlighted in the picture to make effects faster or slower.",
        link: ["lighting", "Set speed"],
      },
      {
        id: "rgb-onoff", title: "Turn lighting on or off", img: "rgb-onoff",
        lead: "Hold the buttons highlighted in the picture for 3 seconds to turn the lights on or off.",
        note: "Or use the Lights switch in this app.",
        link: ["lighting", "Open Lighting"],
      },
    ],
  },
  {
    group: "Hardware",
    topics: [
      {
        id: "weight", title: "Weight balance", img: "weight", extra: "weight-detail",
        lead: "Under the mouse, a screw-in weight moves along a short track. Loosen the screw about 1 mm, slide the weight forward or back, then tighten it again.",
      },
      {
        id: "shell", title: "Swap the back shell", img: "shell-remove", extra: "shell-swap",
        lead: "The M4 comes with a low and a high back shell to change the hump of the mouse.",
        steps: [
          "Remove the screws marked on the underside.",
          "Lift the back shell off, front edge first.",
          "Clip the other shell on and put the screws back.",
        ],
        note: "Xtrfy also publishes 3D (.stp) files of both shells if you want to print or design your own.",
      },
    ],
  },
  {
    group: "Support",
    topics: [
      {
        id: "support", title: "Support and manual", img: "support",
        lead: "For anything this app and the guide don't cover, contact Xtrfy support at support@xtrfy.com.",
        link: ["manual", "Open the full guide"],
      },
    ],
  },
];
