export function applyInitialState(app, data) {
    const graphics = app.stage.getChildAt(0).getChildAt(0);
    graphics.clear();
    data.cells.forEach(([x, y, color]) => {
        graphics.beginFill(color);
        graphics.drawRect(x, y, 1, 1);
        graphics.endFill();
    });
}

export function updateGraphics(app, gridBuffer) {
    const graphics = app.stage.getChildAt(0).getChildAt(0);
    graphics.clear();
    const gridData = new Uint8Array(gridBuffer.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const imageData = pako.inflate(gridData);
    const updateTexture = PIXI.Texture.fromBuffer(imageData, 600, 400);

    if (!graphics.sprite) {
        const sprite = new PIXI.Sprite(updateTexture);
        graphics.sprite = sprite;
        graphics.addChild(sprite);
        sprite.position.set(0, 0);
    } else {
        graphics.sprite.texture = updateTexture;
        graphics.sprite.texture.update();
    }
}

export function updateSquareInfo(app, squareInfo) {
    const textContainer = app.stage.getChildAt(0).getChildAt(1);
    textContainer.removeChildren();

    squareInfo.forEach(({ id, resources, center_of_mass }) => {
        const text = new PIXI.Text(resources.toString(), {
            fontFamily: 'Arial',
            fontSize: 12,
            fill: 0xFFFFFF,
            align: 'center'
        });
        text.anchor.set(0.5);
        text.position.set(center_of_mass[1], center_of_mass[0]);
        textContainer.addChild(text);
    });
}
