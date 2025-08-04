import { reactive } from "@odoo/owl";

export const UserStore = reactive({
    currentUser: null,
    isAuthenticated: false,
});
