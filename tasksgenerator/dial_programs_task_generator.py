"""
dial_programs_tasks_generator.py | Author: Catherine Wong.
Defines TasksGenerators that produce gadgets tasks with dials on them.

Threads program string generating logic through the generation.
"""
import math, random, itertools, copy
from primitives.gadgets_primitives import *
from dreamcoder.grammar import Grammar
from primitives.object_primitives import rectangle
from tasksgenerator.dial_tasks_generator import DIAL_SCALE_UNIT
from tasksgenerator.tasks_generator import (
    AbstractTasksGenerator,
    ManualCurriculumTasksGenerator,
    TasksGeneratorRegistry,
    TaskCurriculum,
    DrawingTask,
    random_sample_ratio_ordered_array,
)
from tasksgenerator.bases_parts_tasks_generator import *

from tasksgenerator.s12_s13_tasks_generator import RANDOM_SEED

@TasksGeneratorRegistry.register
class DialProgramsTasksGenerator(AbstractTasksGenerator):
    name = "dial_programs"

    def __init__(self):
        super().__init__(grammar=constants + some_none + objects + transformations)

    # _generate_base_with_dials
    def _generate_base_with_dials(
        self,
        n_dials,
        n_circles,
        circle_size,
        dial_size,
        dial_angle,
        n_dial_rows=1,
        spacing=LARGE + SCALE_UNIT,
        base_width=LARGE,
        base_height=LARGE,
        base_columns=None,
        n_base_tiers=1,
        centered=False,
        max_dials=3,
        base_end_filials=False,
        shape_specification=None,
        no_base=False,
    ):
        # Generate the x grid.
        # TODO.
        if not no_base:
            base, base_string, base_width, base_height = self._generate_bases_string(
                base_width=base_width,
                base_height=base_height,
                base_columns=base_columns,
                max_rows=n_dial_rows,
                n_tiers=n_base_tiers,
                base_end_filials=base_end_filials,
            )
            stimuli += base

    def _generate_nested_circle_dials_string(
        self,
        n_circles=str(1),
        circle_size=str(SMALL),
        dial_size=str(SMALL),
        dial_angle=STR_VERTICAL,
        shape_specification=None 
    ):
        """
        Generates primitive parts for circular dials: parameterized by
        number of dials to draw left to right, n-nested circles, radius of inner-most circle,
        length of the dial hand (or NONE), and angle of the dial hand.
        Shape specification: array of shapes to draw the dial from.
        
        :ret: dial_strokes, dial_strokes_string
        """
        strokes, stroke_strings = [], []
        if circle_size != STR_ZERO and not shape_specification:
            # Draw nested circles.
            scale_factor = f"(+ {circle_size} {SCALE_UNIT})"
            circle_strokes, circle_strings = nested_scaling_string(c_string[-1], n_circles, scale_factor)
            strokes += circle_strokes
            stroke_strings.append(circle_strings)
        # Shape specification - we don't really do this one correctly.
        if shape_specification:
            for shape_idx, (shape, shape_string) in enumerate(shape_specification):
                scale_factor = f"(+ {circle_size} (* {shape_idx} {SCALE_UNIT}))"
                object_stroke, object_string = T_string(shape, shape_string, s=scale_factor)
                strokes += object_stroke
                stroke_strings.append(object_string)
        
        # Dials.
        if dial_size != STR_ZERO:
            dial_hand, dial_hand_string = T_string(short_l_string[0], short_l_string[-1], theta=dial_angle, s=dial_size)
            dial_x = f"(* {dial_size} (* {SCALE_UNIT} (cos {dial_angle})))"
            dial_y = f"(* {dial_size} (* {SCALE_UNIT} (sin {dial_angle})))"
            dial_hand, dial_hand_string = T_string(dial_hand, dial_hand_string,x=dial_x, y=dial_y)
            strokes += dial_hand 
            stroke_strings.append(dial_hand_string)
        
        return [strokes], connect_strokes(stroke_strings)

    def _generate_bases_string(
        self,
        base_columns=str(3),
        max_rows=str(1),
        base_width=str(LARGE),
        base_height=str(LARGE),
        n_tiers=str(1),
        base_center=str(BASE_CENTER),
        tier_scaling=str(SCALE_UNIT),
        base_end_filials=False
    ):
        """
        Generates bases and a string program that can be evaluated to generate the resulting base.
        See dial_tasks_generator.generate_bases for the original implementation.

        :ret: base, base_string, base_width, base_width_string, base_height, base_height_string. 
        """
        strokes, stroke_strings = [], []
        margins = f"(* 4 {tier_scaling})"
        total_base_height = "0"
        total_base_width = "0"
        tier_offset = "0"

        # Place tiers. Note that we don't currently express the looped computation in a loop.
        first_tier_width, first_tier_height = None, None
        for tier_idx in range(peval(n_tiers)):
            tier_width = f"(+ (* {base_columns} (+ {base_width} {SCALE_UNIT})) {margins})"
            tier_width = f"(- {tier_width} (* {tier_idx} {margins}))"

            tier_height = f"(+ (* {max_rows} (+ {base_width} {SCALE_UNIT})) {margins})"
            tier_height = f"(* {tier_height} (^ {tier_scaling} {tier_idx}))"

            # Hacky: only allows two tiers
            if tier_idx > 0:
                tier_offset = f"(* {SCALE_UNIT} (+ {tier_height} {first_tier_height}))"
            
            tier_y = f"(+ (* 0.5 {base_center}) {tier_offset})"
            tier_rect, tier_rect_string = scaled_rectangle_string(tier_width, tier_height)
            tier_rect, tier_rect_string = T_string(tier_rect, tier_rect_string, y=tier_y)
            strokes += tier_rect
            stroke_strings.append(tier_rect_string)

            total_base_width = "(max {total_base_width} {tier_width})"

            if tier_idx == 0:
                first_tier_width, first_tier_height = tier_width, tier_height
                total_base_height = f"(+ (* 0.5 {tier_height}) {total_base_height})"
            else:
                total_base_height = f"(+ {tier_height} {total_base_height})"
        
        # Add decorative finials.
        if base_end_filials:
            filial_width = f"(* 2 {SCALE_UNIT})"
            filial_height = f"(* {first_tier_height} {SCALE_UNIT})"
            filial_rect, filial_rect_string = scaled_rectangle_string(w=filial_width, h=filial_height)
            x_shift = f"(* 0.5 (+ {first_tier_width} {filial_width}))"
            first_filial, first_filial_string = T_string(filial_rect, filial_rect_string, x=x_shift)

            strokes += first_filial
            stroke_strings.append(first_filial_string)

            x_shift = f"(- 0 {x_shift})"
            scd_filial, scd_filial_string = T_string(filial_rect, filial_rect_string, x=x_shift)
            strokes += scd_filial
            stroke_strings.append(scd_filial_string)

            total_base_width = f"(+ {total_base_width} (* 2 {filial_width}))"

        return strokes, connect_strokes(stroke_strings), total_base_width, total_base_height


