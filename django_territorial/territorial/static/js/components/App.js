import Canvas from './Canvas.js';
import { setupWebSocket } from '../utils/websocket.js';
import { applyMap, updateGraphics, updateSquareInfo } from '../utils/pixiHelpers.js';

const { useEffect, useState, createElement } = React;

export default function App() {
    const [app, setApp] = useState(null);
    const [socket, setSocket] = useState(null);

    useEffect(() => {
        if (app) {
            const newSocket = setupWebSocket(handleSocketMessage);
            setSocket(newSocket);

            return () => {
                if (newSocket) newSocket.close();
            };
        }
    }, [app]);  // Only set up WebSocket after app is initialized

    const handleSocketMessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'map') {
            applyMap(app, data.grid);
        } else if (data.type === 'square_info') {
            updateSquareInfo(app, data.square_info);
        } else if (data.type === 'grid_update') {
            updateGraphics(app, data.grid);
        }
    };

    return createElement(Canvas, { setApp: setApp });
}
