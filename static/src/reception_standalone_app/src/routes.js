/** @odoo-module **/

import { HomePage } from "./pages/home";
import { AboutPage } from "./pages/about";
import { RoomsPage } from "./pages/rooms";
import { Reservations } from "./pages/reservations";
import { TestRPC } from "./pages/test_rpc";

export function setupRouter(state) {
  const page = window.page;

  if (!page) {
    console.error("❌ page.js non chargé !");
    return;
  }

  console.log("🧭 Initialisation du router...");

  page("/", () => {
    console.log("➡️ Route / (home)");
    state.currentComponent.set(HomePage);
    state.currentProps.set({});
  });

  page("/about", () => {
    console.log("➡️ Route /about");
    state.currentComponent.set(AboutPage);
    state.currentProps.set({});
  });

  page("/about/:name", (ctx) => {
    console.log("➡️ Route /about/:name", ctx.params);
    state.currentComponent.set(AboutPage);
    state.currentProps.set({ name: ctx.params.name });
  });
   page("/rooms", () => {
    console.log("➡️ Route /rooms");
    state.currentComponent.set(RoomsPage);
    state.currentProps.set({});
  });

  page("/bookings", () => {
    console.log("➡️ Route /bookings");
    state.currentComponent.set(Reservations);
    state.currentProps.set({});
  });
    page("/test", () => {
    console.log("➡️ Route /test");
    state.currentComponent.set(TestRPC);
    state.currentProps.set({});
  });

  page("*", () => {
    console.warn("❓ Route non trouvée !");
    state.currentComponent.set(HomePage);
    state.currentProps.set({});
  });
 

  page(); // démarre l'écoute des changements de route
}
