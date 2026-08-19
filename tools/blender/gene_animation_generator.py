"""Generate a starter Gené animation action set from an MMD Tools model.

Run from Blender's Scripting workspace with the Gené armature/model loaded.
The script does not require existing Actions. It creates reusable Actions for
idle, talking, thinking, happy, surprised, sad, angry, sleepy and greeting.

Morph names differ between MMD models, so facial morph matching is deliberately
best-effort. The script prints discovered morph names and safely skips missing
ones. Body motion uses bones when recognizable MMD bone names are found.
"""
import bpy
import math

FPS = 30
FRAME_COUNTS = {
    "Gene_IDLE": 120,
    "Gene_TALKING": 60,
    "Gene_THINKING": 90,
    "Gene_HAPPY": 90,
    "Gene_SURPRISED": 60,
    "Gene_SAD": 90,
    "Gene_ANGRY": 60,
    "Gene_SLEEPY": 120,
    "Gene_GREETING": 90,
}

# Common Japanese/English MMD morph keywords. Exact names are model-dependent.
MORPH_ALIASES = {
    "smile": ["smile", "笑い", "にっこり", "smile1"],
    "mouth": ["mouth", "口", "あ", "あー", "口開き"],
    "blink": ["blink", "まばたき", "目閉じ", "目_閉じ"],
    "surprise": ["surprise", "驚き", "びっくり"],
    "sad": ["sad", "悲しい", "困る"],
    "angry": ["angry", "怒り", "怒る"],
}

BONE_ALIASES = {
    "head": ["頭", "head"],
    "neck": ["首", "neck"],
    "chest": ["上半身", "上半身2", "chest", "spine"],
    "left_arm": ["左腕", "左腕", "arm.L", "左ひじ"],
    "right_arm": ["右腕", "右腕", "arm.R", "右ひじ"],
}


def find_armature():
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            return obj
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None


def norm(value):
    return str(value).lower().replace('_', '').replace('-', '').replace(' ', '')


def find_key(items, aliases):
    normalized = [(norm(x), x) for x in items]
    for alias in aliases:
        a = norm(alias)
        for n, original in normalized:
            if a == n or a in n or n in a:
                return original
    return None


def morph_objects(armature):
    result = []
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.data.shape_keys:
            result.append(obj)
    return result


def find_morph(armature, aliases):
    for obj in morph_objects(armature):
        names = [k.name for k in obj.data.shape_keys.key_blocks if k.name != 'Basis']
        found = find_key(names, aliases)
        if found:
            return obj, found
    return None, None


def key_morph(obj, name, frame, value):
    block = obj.data.shape_keys.key_blocks.get(name)
    if block:
        block.value = value
        block.keyframe_insert(data_path='value', frame=frame)


def key_bone_rotation(armature, bone_name, frame, x=0, y=0, z=0):
    if not bone_name or bone_name not in armature.pose.bones:
        return
    bone = armature.pose.bones[bone_name]
    bone.rotation_mode = 'XYZ'
    bone.rotation_euler = (x, y, z)
    bone.keyframe_insert(data_path='rotation_euler', frame=frame)


def action(armature, name, end):
    armature.animation_data_create()
    act = bpy.data.actions.get(name) or bpy.data.actions.new(name)
    act.use_fake_user = True
    armature.animation_data.action = act
    for fc in list(act.fcurves):
        act.fcurves.remove(fc)
    return act


def make_action(armature, name, end, pose_fn):
    act = action(armature, name, end)
    for frame in range(1, end + 1):
        pose_fn(frame, end)
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
    return act


def main():
    arm = find_armature()
    if not arm:
        raise RuntimeError('No armature found. Select the Gené armature and run again.')

    print('\n=== Gené animation generator ===')
    print('Armature:', arm.name)
    for obj in morph_objects(arm):
        print('Morph mesh:', obj.name)
        print('  ', [k.name for k in obj.data.shape_keys.key_blocks if k.name != 'Basis'][:80])

    bones = [b.name for b in arm.pose.bones]
    head = find_key(bones, BONE_ALIASES['head'])
    neck = find_key(bones, BONE_ALIASES['neck'])
    chest = find_key(bones, BONE_ALIASES['chest'])
    left_arm = find_key(bones, BONE_ALIASES['left_arm'])
    right_arm = find_key(bones, BONE_ALIASES['right_arm'])
    print('Bones:', {'head': head, 'neck': neck, 'chest': chest, 'left_arm': left_arm, 'right_arm': right_arm})

    morph = {k: find_morph(arm, v) for k, v in MORPH_ALIASES.items()}
    print('Matched morphs:', {k: v[1] for k, v in morph.items() if v[1]})

    def set_m(name, frame, value):
        obj, key = morph.get(name, (None, None))
        if obj and key:
            key_morph(obj, key, frame, value)

    def common(frame, end):
        t = (frame - 1) / max(1, end - 1)
        bob = math.sin(t * math.tau * 2.0) * math.radians(1.5)
        key_bone_rotation(arm, chest, frame, x=bob)
        key_bone_rotation(arm, head, frame, z=math.sin(t * math.tau) * math.radians(1.5))
        if frame in (1, end):
            set_m('blink', frame, 0.0)
        blink_start = max(2, int(end * 0.42))
        if blink_start <= frame <= blink_start + 3:
            set_m('blink', frame, min(1.0, (frame - blink_start + 1) / 2.0))
        elif frame == blink_start + 4:
            set_m('blink', frame, 0.0)

    def idle(frame, end):
        common(frame, end)

    def talking(frame, end):
        common(frame, end)
        phase = (frame % 8) / 7.0
        set_m('mouth', frame, 0.25 + 0.6 * phase)

    def thinking(frame, end):
        common(frame, end)
        key_bone_rotation(arm, head, frame, z=math.radians(6) * math.sin((frame / end) * math.pi))

    def happy(frame, end):
        common(frame, end)
        set_m('smile', frame, 0.8)
        set_m('mouth', frame, 0.15)

    def surprised(frame, end):
        common(frame, end)
        set_m('surprise', frame, 0.9)
        set_m('mouth', frame, 0.8)

    def sad(frame, end):
        common(frame, end)
        set_m('sad', frame, 0.8)
        key_bone_rotation(arm, head, frame, z=math.radians(-5))

    def angry(frame, end):
        common(frame, end)
        set_m('angry', frame, 0.9)

    def sleepy(frame, end):
        common(frame, end)
        set_m('blink', frame, 1.0)
        key_bone_rotation(arm, head, frame, z=math.radians(-3))

    def greeting(frame, end):
        common(frame, end)
        wave = math.sin((frame / end) * math.tau * 2.0) * math.radians(18)
        key_bone_rotation(arm, right_arm, frame, z=wave)
        set_m('smile', frame, 0.6)

    poses = {
        'Gene_IDLE': idle,
        'Gene_TALKING': talking,
        'Gene_THINKING': thinking,
        'Gene_HAPPY': happy,
        'Gene_SURPRISED': surprised,
        'Gene_SAD': sad,
        'Gene_ANGRY': angry,
        'Gene_SLEEPY': sleepy,
        'Gene_GREETING': greeting,
    }

    for name, end in FRAME_COUNTS.items():
        print('Creating', name)
        make_action(arm, name, end, poses[name])

    arm.animation_data.action = bpy.data.actions.get('Gene_IDLE')
    bpy.context.scene.render.fps = FPS
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = FRAME_COUNTS['Gene_IDLE']
    print('Done. Actions created:', ', '.join(FRAME_COUNTS))


if __name__ == '__main__':
    main()
