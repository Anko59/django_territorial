import Canvas from './Canvas.js';
import { setupWebSocket } from '../utils/websocket.js';
import { applyInitialState, updateGraphics, updateSquareInfo } from '../utils/pixiHelpers.js';

const { useEffect, useState } = React;

export default function App() {
    const [app, setApp] = useState(null);
    const [socket, setSocket] = useState(null);

    useEffect(() => {
        const newSocket = setupWebSocket(handleSocketMessage);
        setSocket(newSocket);

        return () => {
            if (newSocket) newSocket.close();
        };
    }, []);

    const handleSocketMessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'initial_state') {
            applyInitialState(app, data);
        } else if (data.type === 'update') {
            // Handle updates
        } else if (data.type === 'square_info') {
            updateSquareInfo(app, data.square_info);
        } else if (data.type === 'grid_update') {
            updateGraphics(app, data.grid);
        }
    };

    return React.createElement(Canvas, { setApp: setApp });
}
