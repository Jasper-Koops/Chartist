import { createHomeState } from "./home/state.js";
import { createOverview } from "./home/overview.js";
import { createMap } from "./home/map.js";
import { registerHomeNavigation } from "./home/navigation.js";

const state = createHomeState();
const overview = createOverview(state);
const map = createMap(state, overview.renderAxes);
registerHomeNavigation(state, map, overview);
