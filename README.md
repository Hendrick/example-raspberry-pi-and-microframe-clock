# example-raspberry-pi-and-microframe-clock

This python script is an example of how to use a raspberry pi to control Microframe clock displays through opening and closing of relays.  This example was created to allow for a scorekeeper to press a single button to start/stop to sets of Microframe clocks (1 for each team).  Additionally, there is the ability to start/stop individual team clocks as well as reset all of the clocks.

The relays are connected to the Microframe clocks via their terminal blocks on the back of the clocks.  This simulates the pressing of a button when the relay is closed.

Lines 122 - 212 contain the methods that are used to work with the clocks.

To see how these are used in production, you can watch a recent compentition at https://www.hendrickebs.com
