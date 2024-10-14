const { WIDTH: GAME_WIDTH, HEIGHT: GAME_HEIGHT } = window.GAME_CONFIG;


export function applyMap(app, data) {
    if (!app || !app.stage) return;
    const graphics = app.stage.getChildAt(0).getChildAt(0);
    graphics.clear();
    const gridData = new Uint8Array(data.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const imageData = pako.inflate(gridData);
    const mapTexture = PIXI.Texture.fromBuffer(imageData, GAME_WIDTH, GAME_HEIGHT);
    const mapSprite = new PIXI.Sprite(mapTexture);
    graphics.addChild(mapSprite);
    mapSprite.position.set(0, 0);
}

export function updateGraphics(app, gridBuffer) {
    if (!app || !app.stage) return;
    const graphics = app.stage.getChildAt(0).getChildAt(0);
    graphics.clear();
    let gridData = new Uint8Array(gridBuffer.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    let imageData = pako.inflate(gridData);
    const updateTexture = PIXI.Texture.fromBuffer(imageData, GAME_WIDTH, GAME_HEIGHT);

    if (!graphics.sprite) {
        const sprite = new PIXI.Sprite(updateTexture);
        graphics.sprite = sprite;
        graphics.addChild(sprite);
        sprite.position.set(0, 0);
    } else {
        graphics.sprite.texture.destroy();
        graphics.sprite.texture = updateTexture;
        graphics.sprite.texture.update();
    }
    gridBuffer = null;
    imageData = null;
    gridData = null;
    PIXI.utils.clearTextureCache();
}

export function updateSquareInfo(app, squareInfo) {
    if (!app || !app.stage) return;
    const textContainer = app.stage.getChildAt(0).getChildAt(1);
    textContainer.removeChildren();

    const totalArea = GAME_WIDTH * GAME_HEIGHT;
    const maxFontSize = 35;
    const minFontSize = 1;

    squareInfo.forEach(({ id, resources, center_of_mass, name, area, average_land_value }) => {
        const scaleFactor = Math.sqrt(area / totalArea);
        const fontSize = Math.max(minFontSize, Math.min(maxFontSize, Math.floor(scaleFactor * 200)));
        if (fontSize > 3) {
            const nameText = new PIXI.Text(name, {
                fontFamily: 'Arial',
                fontSize: fontSize,
                fontWeight: 'bold',
                fill: 0xFFFFFF,
                align: 'center'
            });
            nameText.anchor.set(0.5, 1);
            nameText.position.set(center_of_mass[1], center_of_mass[0]);

            const resourceText = new PIXI.Text(resources.toString(), {
                fontFamily: 'Arial',
                fontSize: Math.max(minFontSize, fontSize - 2),
                fill: 0xFFFFFF,
                align: 'center'
            });
            resourceText.anchor.set(0.5, 0);
            resourceText.position.set(center_of_mass[1], center_of_mass[0] + 2);

            textContainer.addChild(nameText);
            textContainer.addChild(resourceText);
        }
    });

    updateLeaderboard(app, squareInfo);
}

export function updateBoats(app, boats) {
    if (!app || !app.stage) return;
    const boatContainer = app.stage.getChildAt(0).getChildAt(3) || new PIXI.Container();

    boatContainer.removeChildren();


    boats.forEach(({ pos, speed, investment, color }) => {
        const boat = new PIXI.Graphics();

        // Convert color array to hexadecimal
        let hexColor;
        if (Array.isArray(color) && color.length >= 3) {
            // Ensure RGB values are within 0-255 range
            const r = Math.min(255, Math.max(0, color[0]));
            const g = Math.min(255, Math.max(0, color[1]));
            const b = Math.min(255, Math.max(0, color[2]));

            // Convert to hex
            hexColor = (r << 16) + (g << 8) + b;
        } else {
            // Default color if conversion fails
            hexColor = 0xFFFFFF;
        }
        boat.beginFill(hexColor);
        boat.drawPolygon([-5, -5, 5, 0, -5, 5]);
        boat.endFill();
        boat.position.set(pos[1], pos[0]);
        boat.rotation = Math.atan2(speed[1], speed[0]);
        boatContainer.addChild(boat);
    });
}
function updateLeaderboard(app, squareInfo) {
    const leaderboardContainer = app.stage.getChildAt(0).getChildAt(2) || new PIXI.Container();
    if (!app.stage.getChildAt(0).getChildAt(2)) {
        app.stage.getChildAt(0).addChild(leaderboardContainer);
    }
    leaderboardContainer.removeChildren();

    const sortedSquares = squareInfo.sort((a, b) =>
        (b.area * b.average_land_value) - (a.area * a.average_land_value)
    ).slice(0, 10);

    const leaderboardTitle = new PIXI.Text("Leaderboard", {
        fontFamily: 'Arial',
        fontSize: 18,
        fontWeight: 'bold',
        fill: 0xFFFFFF,
    });
    leaderboardTitle.position.set(10, GAME_HEIGHT - 220);
    leaderboardContainer.addChild(leaderboardTitle);

    sortedSquares.forEach((square, index) => {
        const totalValue = Math.round(square.area * square.average_land_value);
        const text = new PIXI.Text(`${index + 1}. ${square.name} (${square.area}, $${totalValue})`, {
            fontFamily: 'Arial',
            fontSize: 12,
            fill: 0xFFFFFF,
        });
        text.position.set(10, GAME_HEIGHT - 190 + index * 20);
        leaderboardContainer.addChild(text);
    });
}
