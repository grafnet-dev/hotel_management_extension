import { reactive } from "@odoo/owl";

export const UIStore = reactive({
    sidebarOpen: true,
    loading: {
        rooms: false,
        reservations: false,
    },
    filters: {
        reservationType: 'all',  // 'dayuse', 'overnight', 'flexible'
        roomStatus: 'available', // ou 'all'
    },
    modals: {
        showRoomDetails: false,
        currentRoomId: null,
    },
    toast: null, // { type: 'success', message: '...' }
});
