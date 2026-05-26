// Copyright (c) 2019-2020 X, The Moonshot Factory (USA).
// All rights reserved.
//
// This file is part of CGAL (www.cgal.org).
//
// $URL: https://github.com/CGAL/cgal/blob/v6.2-beta1/Alpha_wrap_2/demo/Alpha_wrap_2/Alpha_wrap_2_options.h $
// $Id: demo/Alpha_wrap_2/Alpha_wrap_2_options.h 431cfb5357d $
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Author(s)     : Pierre Alliez pierre.alliez@inria.fr
//               : Michael Hemmer mhsaar@gmail.com
//               : Cedric Portaneri cportaneri@gmail.com
//
#ifndef CGAL_ALPHA_WRAP_2_DEMO_OPTIONS_H
#define CGAL_ALPHA_WRAP_2_DEMO_OPTIONS_H

#include "ui_Alpha_wrap_2_options.h"

/**
 * @class AlphaWrapOptions
 * @brief Interface to tune the alpha wrapping options
 */
class AlphaWrapOptions
  : public QDialog, private Ui::AlphaWrapOptions
{
  Q_OBJECT

 public:
  AlphaWrapOptions(QWidget*, double alpha, double offset,
                   bool is_alpha_relative,
                   bool is_offset_relative,
                   bool step_by_step)
  {
    setupUi(this);
    alphaValue->setValue(alpha);
    offsetValue->setValue(offset);
    radioButtonAlphaAbs->setChecked(!is_alpha_relative);
    radioButtonAlphaRel->setChecked(is_alpha_relative);
    radioButtonOffsetAbs->setChecked(!is_offset_relative);
    radioButtonOffsetRel->setChecked(is_offset_relative);
    stepByStepCheckBox->setChecked(step_by_step);
  }

  bool is_alpha_relative() {
    return radioButtonAlphaRel->isChecked();
  }

  double get_alpha_value() {
    return alphaValue->value();
  }

  bool is_offset_relative() {
    return radioButtonOffsetRel->isChecked();
  }

  double get_offset_value() {
    return offsetValue->value();
  }

  bool is_step_by_step() {
    return stepByStepCheckBox->isChecked();
  }
};

#endif  // CGAL_ALPHA_WRAP_2_DEMO_OPTIONS_H
