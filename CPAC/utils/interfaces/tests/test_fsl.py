from ..fsl import Merge


def test_Merge_inputs():
    input_map = dict(
        args=dict(
            argstr="%s",
        ),
        dimension=dict(
            argstr="-%s",
            mandatory=True,
            position=0,
        ),
        environ=dict(
            nohash=True,
            usedefault=True,
        ),
        in_files=dict(
            argstr="%s",
            mandatory=True,
            position=2,
        ),
        merged_file=dict(
            argstr="%s",
            extensions=None,
            hash_files=False,
            name_source="in_files",
            name_template="%s_merged",
            position=1,
        ),
        output_type=dict(),
        tr=dict(
            argstr="%.2f",
            position=-1,
        ),
    )
    inputs = Merge.input_spec()

    for key, metadata in list(input_map.items()):
        for metakey, value in list(metadata.items()):
            assert getattr(inputs.traits()[key], metakey) == value


def test_Merge_outputs():
    output_map = dict(
        merged_file=dict(
            extensions=None,
        ),
    )
    outputs = Merge.output_spec()

    for key, metadata in list(output_map.items()):
        for metakey, value in list(metadata.items()):
            assert getattr(outputs.traits()[key], metakey) == value